"""Reflexion critic: taxonomy-classified root-cause replanning (#15).

On a verification failure, instead of a naive retry this classifies the
failure against the taxonomy, retrieves the nearest corpus tuple, and emits a
*targeted* replan addressing that specific root cause. A corpus-grounded step
(a verified prior fix) makes the replan targeted rather than a guess; the
resolution, once it works, feeds a new corpus tuple. This is what separates
"loop until budget" from converging intelligently.
"""

from dataclasses import dataclass, field
from typing import Any

import structlog

from deepgent.telemetry.taxonomy import classify_failure

_logger = structlog.get_logger(__name__)

# Deterministic tag -> next-action guidance when the corpus has no match.
_TAG_ADVICE: dict[str, str] = {
    "build_toolchain": "rebuild inside the pinned toolchain container; do not use host tools",
    "build_deps": "resolve the missing/conflicting dependency against versions.toml, then rebuild",
    "static_analysis": "fix the reported violations at the source; never suppress them",
    "unit_test": "reproduce the failing assertion and fix the root cause, not the test",
    "deploy_ssh": "verify board reachability and key auth; check the watchdog timeout",
    "runtime_crash": "capture the backtrace and check for null/uninitialized or OOB state",
    "perf_miss": "profile with nsight to locate the bottleneck before micro-optimizing",
    "accuracy_miss": "run the accuracy gate vs baseline; check the INT8 calibration set",
    "thermal": "drop to a lower power mode or improve cooling; re-run the thermal envelope",
    "flaky_hw": "re-run under the soak harness to confirm; check power/thermal stability",
    "knowledge_gap": "query the datasheet RAG for the missing fact; do not guess it",
    "harness_bug": "the fault is in deepgent's harness, not the target; fix the harness",
}
_UNCLASSIFIED_ADVICE = "inspect the raw error, isolate the smallest failing step, and address it"


@dataclass(frozen=True)
class ReplanStep:
    """One targeted action for the next attempt."""

    action: str
    rationale: str
    from_corpus: bool

    def render(self) -> str:
        tag = " [corpus-verified]" if self.from_corpus else ""
        return f"- {self.action}{tag}\n    why: {self.rationale}"


@dataclass
class Reflexion:
    """A classified failure plus a targeted replan."""

    failure_tag: str | None
    steps: list[ReplanStep] = field(default_factory=list)
    corpus_match: dict[str, Any] | None = None

    @property
    def targeted(self) -> bool:
        """True when at least one step is grounded in a verified prior fix."""
        return any(step.from_corpus for step in self.steps)

    def to_dict(self) -> dict[str, object]:
        return {
            "failure_tag": self.failure_tag,
            "targeted": self.targeted,
            "corpus_match": self.corpus_match,
            "steps": [
                {"action": s.action, "rationale": s.rationale, "from_corpus": s.from_corpus}
                for s in self.steps
            ],
        }

    def render(self) -> str:
        lines = [
            "# reflexion",
            f"failure class: {self.failure_tag or 'unclassified'}",
            f"targeted: {'yes (corpus-grounded)' if self.targeted else 'no (heuristic)'}",
            "",
            "replan:",
        ]
        lines += [s.render() for s in self.steps]
        return "\n".join(lines) + "\n"


def reflect(
    tool_name: str, error: str, corpus_tuples: list[dict[str, Any]] | None = None
) -> Reflexion:
    """Classify the failure and build a targeted replan.

    A corpus tuple, when present, yields a verified-fix step and makes the
    replan targeted; otherwise a deterministic tag-based step is used.
    """
    tag = classify_failure(tool_name, error)
    reflexion = Reflexion(failure_tag=tag)
    match = corpus_tuples[0] if corpus_tuples else None
    if match is not None:
        reflexion.corpus_match = match
        reflexion.steps.append(
            ReplanStep(
                action=str(match.get("fix", "apply the verified prior fix")),
                rationale=(
                    f"a prior failure ('{match.get('symptom', '')}') was resolved this way "
                    f"(verified by {match.get('verification_run_id', 'corpus')})"
                ),
                from_corpus=True,
            )
        )
    advice = _TAG_ADVICE.get(tag or "", _UNCLASSIFIED_ADVICE)
    reflexion.steps.append(
        ReplanStep(
            action=advice,
            rationale=f"deterministic guidance for failure class '{tag or 'unclassified'}'",
            from_corpus=False,
        )
    )
    _logger.info("reflexion", failure_tag=tag, targeted=reflexion.targeted)
    return reflexion


async def reflect_with_corpus(
    client: Any, tool_name: str, error: str, hw: str | None = None
) -> Reflexion:
    """Search the corpus for the error symptom, then reflect."""
    tuples = await client.search_symptom(error, hw=hw)
    return reflect(tool_name, error, tuples)
