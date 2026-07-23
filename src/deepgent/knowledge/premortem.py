"""Predictive pre-mortem planner (#11).

Before the architect plans, query the failure corpus and compatibility matrix
for this task's hardware x version cell and surface the failure modes seen
there, each with its verified fix. This turns the corpus from a post-hoc
lookup into forward reasoning: the plan avoids failures already seen instead of
rediscovering them. Every risk carries provenance; none is model opinion.
"""

from dataclasses import dataclass, field
from typing import Any

import structlog

from deepgent.knowledge.rag import RagClient

_logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class PredictedRisk:
    """One failure mode predicted for this task, with its known fix."""

    symptom: str
    root_cause: str
    fix: str
    provenance: str
    source: str  # "corpus" | "matrix"

    def render(self) -> str:
        return (
            f"- risk: {self.symptom}\n"
            f"    cause: {self.root_cause}\n"
            f"    mitigation: {self.fix}\n"
            f"    evidence: {self.provenance} ({self.source})"
        )


@dataclass
class PreMortem:
    """Predicted risks for a task, assembled from corpus and matrix."""

    risks: list[PredictedRisk] = field(default_factory=list)

    @property
    def empty(self) -> bool:
        return not self.risks

    def to_dict(self) -> dict[str, object]:
        return {
            "risks": [
                {
                    "symptom": r.symptom,
                    "root_cause": r.root_cause,
                    "fix": r.fix,
                    "provenance": r.provenance,
                    "source": r.source,
                }
                for r in self.risks
            ]
        }

    def render(self) -> str:
        if self.empty:
            return "# pre-mortem\n\nNo prior failures match this task's hardware and stack.\n"
        lines = ["# pre-mortem: predicted failure modes", ""]
        lines += [r.render() for r in self.risks]
        lines.append("")
        lines.append("Fold these mitigations into the plan before execution.")
        return "\n".join(lines) + "\n"

    def plan_prelude(self) -> str:
        """Compact text to prepend to an architect delegation prompt."""
        if self.empty:
            return ""
        bullets = "\n".join(
            f"- {r.symptom}: apply '{r.fix}' (seen in {r.provenance})" for r in self.risks
        )
        return (
            "Known failure modes for this hardware/stack (from the failure "
            f"corpus and compatibility matrix); pre-empt them in the plan:\n{bullets}\n"
        )


def assemble_premortem(
    corpus_tuples: list[dict[str, Any]], matrix_claim: dict[str, Any] | None
) -> PreMortem:
    """Pure assembly of predicted risks from corpus hits and a matrix claim."""
    premortem = PreMortem()
    for tup in corpus_tuples:
        premortem.risks.append(
            PredictedRisk(
                symptom=str(tup.get("symptom", "")),
                root_cause=str(tup.get("root_cause", "")),
                fix=str(tup.get("fix", "")),
                provenance=str(tup.get("verification_run_id", "corpus")),
                source="corpus",
            )
        )
    if matrix_claim and matrix_claim.get("status") == "verified_fail":
        premortem.risks.append(
            PredictedRisk(
                symptom=str(matrix_claim.get("claim", "known-incompatible stack")),
                root_cause="the compatibility matrix records this exact stack as verified_fail",
                fix="change the stack to a verified_pass combination or verify empirically first",
                provenance=str(matrix_claim.get("evidence_run_id", "matrix")),
                source="matrix",
            )
        )
    return premortem


async def premortem(
    client: RagClient,
    symptom: str,
    hw: str | None = None,
    stack: dict[str, str] | None = None,
) -> PreMortem:
    """Corpus + matrix pre-mortem for a task; corpus-first, provenance-carried."""
    tuples = await client.search_symptom(symptom, hw=hw)
    matrix_claim: dict[str, Any] | None = None
    if stack:
        claim = await client.query_claim(stack)
        matrix_claim = claim or None
    _logger.info("premortem", corpus_hits=len(tuples), has_stack=bool(stack))
    return assemble_premortem(tuples, matrix_claim)
