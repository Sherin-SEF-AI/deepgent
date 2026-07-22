"""Tier 2 knowledge products: upgrade-check, BOM advisor, triage.

These render the compatibility matrix, failure corpus, and golden baselines
into decision artifacts. Every claim they surface carries its evidence
(matrix evidence_run_id, corpus verification_run_id, golden baseline); none
is model opinion. Triage is corpus-first: the deterministic corpus is
consulted before any LLM reasoning, and only a corpus miss escalates.
"""

from dataclasses import dataclass, field
from typing import Any

import structlog

from deepgent.knowledge.rag import RagClient

_logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class UpgradeImpact:
    """One stack component's verified impact under a proposed version move."""

    component: str
    from_version: str
    to_version: str
    status: str  # verified_pass | verified_fail | unknown
    evidence_run_id: str | None
    note: str


@dataclass
class UpgradeReport:
    """Verified impact report for a proposed version move."""

    impacts: list[UpgradeImpact] = field(default_factory=list)

    @property
    def safe(self) -> bool:
        return all(i.status == "verified_pass" for i in self.impacts)

    @property
    def has_unknowns(self) -> bool:
        return any(i.status == "unknown" for i in self.impacts)

    def render(self) -> str:
        lines = ["# upgrade impact report", ""]
        for impact in self.impacts:
            mark = {
                "verified_pass": "PASS",
                "verified_fail": "FAIL",
                "unknown": "UNKNOWN",
            }[impact.status]
            evidence = f" (evidence {impact.evidence_run_id})" if impact.evidence_run_id else ""
            lines.append(
                f"{mark:8s} {impact.component}: {impact.from_version} -> "
                f"{impact.to_version}{evidence}"
            )
            lines.append(f"         {impact.note}")
        lines.append("")
        if self.safe:
            lines.append("VERDICT: every affected claim is verified_pass")
        elif self.has_unknowns:
            lines.append(
                "VERDICT: unverified components remain; run the golden suite on "
                "the target stack before upgrading"
            )
        else:
            lines.append("VERDICT: at least one component is verified_fail; do not upgrade")
        return "\n".join(lines) + "\n"


async def upgrade_check(
    client: RagClient,
    current_stack: dict[str, str],
    proposed: dict[str, str],
) -> UpgradeReport:
    """Query the matrix for each component that changes between the current
    and proposed stacks."""
    report = UpgradeReport()
    for component, new_version in proposed.items():
        old_version = current_stack.get(component, "unset")
        if old_version == new_version:
            continue
        target_stack = {**current_stack, component: new_version}
        claim = await client.query_claim(target_stack)
        status = claim.get("status", "unknown")
        report.impacts.append(
            UpgradeImpact(
                component=component,
                from_version=old_version,
                to_version=new_version,
                status=status,
                evidence_run_id=claim.get("evidence_run_id"),
                note=str(claim.get("claim", "no verified claim for this stack")),
            )
        )
    return report


@dataclass(frozen=True)
class BomConstraints:
    """Requirements a candidate stack must satisfy."""

    min_fps: float | None = None
    max_power_w: float | None = None
    max_cost_usd: float | None = None


@dataclass(frozen=True)
class BomCandidate:
    """One verified stack option with its evidence."""

    board: str
    stack: dict[str, str]
    fps: float | None
    power_w: float | None
    cost_usd: float | None
    evidence_run_id: str

    def satisfies(self, constraints: BomConstraints) -> bool:
        fails_fps = constraints.min_fps is not None and (
            self.fps is None or self.fps < constraints.min_fps
        )
        fails_power = constraints.max_power_w is not None and (
            self.power_w is None or self.power_w > constraints.max_power_w
        )
        fails_cost = constraints.max_cost_usd is not None and (
            self.cost_usd is None or self.cost_usd > constraints.max_cost_usd
        )
        return not (fails_fps or fails_power or fails_cost)


def bom_advise(candidates: list[BomCandidate], constraints: BomConstraints) -> list[BomCandidate]:
    """Verified candidate stacks meeting the constraints, cheapest first.

    Candidates come from verified runs only (each carries evidence_run_id);
    this never invents a stack, it filters measured ones.
    """
    passing = [c for c in candidates if c.satisfies(constraints)]
    return sorted(passing, key=lambda c: c.cost_usd if c.cost_usd is not None else 1e12)


@dataclass(frozen=True)
class TriageResult:
    """Corpus-first debugging outcome."""

    corpus_hit: bool
    tuples: list[dict[str, Any]]
    escalate: bool

    def render(self) -> str:
        if self.corpus_hit:
            lines = ["# triage: corpus hit (no LLM call needed)", ""]
            for tup in self.tuples:
                lines.append(f"symptom: {tup.get('symptom', '')}")
                lines.append(f"root cause: {tup.get('root_cause', '')}")
                lines.append(f"fix: {tup.get('fix', '')}")
                lines.append(f"verified by: {tup.get('verification_run_id', '')}")
                lines.append("")
            return "\n".join(lines)
        return (
            "# triage: corpus miss\n\n"
            "No prior resolved failure matches this symptom. Escalating to "
            "LLM-assisted debugging; the resolution, once verified, becomes a "
            "new corpus tuple.\n"
        )


async def triage(client: RagClient, symptom: str, hw: str | None = None) -> TriageResult:
    """Corpus-first: consult the deterministic failure corpus before any LLM
    reasoning. Only a miss escalates."""
    tuples = await client.search_symptom(symptom, hw=hw)
    hit = len(tuples) > 0
    _logger.info("triage", corpus_hit=hit, symptom_len=len(symptom))
    return TriageResult(corpus_hit=hit, tuples=tuples, escalate=not hit)
