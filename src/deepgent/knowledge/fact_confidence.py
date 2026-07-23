"""Confidence-calibrated fact arbitration (#12).

Every hardware assertion carries a calibrated confidence tied to its
provenance: empirical on-target (highest), datasheet RAG, failure corpus,
matrix inference, and model-memory (refused outright per the constitution).
When sources disagree about the same fact, the highest-confidence source wins
and the conflict is surfaced. Confidence is not fixed: a calibrator learns
each source's observed reliability from recorded outcomes and blends it into
the base, so stated confidence tracks reality.
"""

from dataclasses import dataclass, field

# Base confidence per provenance source. model_memory is 0.0 by design:
# section 1 forbids asserting a hardware fact from model memory.
SOURCE_BASE_CONFIDENCE: dict[str, float] = {
    "empirical": 1.0,
    "datasheet_rag": 0.9,
    "corpus": 0.7,
    "matrix_inferred": 0.5,
    "model_memory": 0.0,
}
REFUSED_SOURCES = frozenset({"model_memory"})
_DEFAULT_BASE = 0.3
# How strongly learned reliability pulls the base confidence.
_CALIBRATION_WEIGHT = 0.5


def confidence_for(
    source: str,
    base_override: float | None = None,
    calibration: dict[str, float] | None = None,
) -> float:
    """Calibrated confidence for a source, in [0, 1].

    Starts from the source's base (or an explicit override, e.g. a matrix
    inference's own confidence) and blends toward learned reliability when the
    calibrator has enough samples for that source.
    """
    base = (
        base_override
        if base_override is not None
        else SOURCE_BASE_CONFIDENCE.get(source, _DEFAULT_BASE)
    )
    if source in REFUSED_SOURCES:
        return 0.0
    if calibration and source in calibration:
        reliability = calibration[source]
        base = (1.0 - _CALIBRATION_WEIGHT) * base + _CALIBRATION_WEIGHT * reliability
    return max(0.0, min(1.0, base))


@dataclass(frozen=True)
class FactAssertion:
    """One source's claim about a subject's value."""

    subject: str
    value: str
    source: str
    base_override: float | None = None

    def resolved_confidence(self, calibration: dict[str, float] | None = None) -> float:
        return confidence_for(self.source, self.base_override, calibration)


@dataclass(frozen=True)
class ArbitratedFact:
    """The arbitrated answer for one subject."""

    subject: str
    value: str | None
    confidence: float
    source: str | None
    conflict: bool
    refused: tuple[str, ...] = ()

    @property
    def known(self) -> bool:
        return self.value is not None

    def render(self) -> str:
        if not self.known:
            reason = f" (refused sources: {', '.join(self.refused)})" if self.refused else ""
            return f"{self.subject}: unknown{reason}\n"
        flag = "  [CONFLICT: sources disagree]" if self.conflict else ""
        return (
            f"{self.subject}: {self.value}  "
            f"(confidence {self.confidence:.2f} via {self.source}){flag}\n"
        )


def arbitrate(
    assertions: list[FactAssertion],
    calibration: dict[str, float] | None = None,
    conflict_threshold: float = 0.3,
) -> ArbitratedFact:
    """Pick the highest-confidence non-refused assertion for one subject.

    A conflict is flagged when another assertion above conflict_threshold
    proposes a different value. Refused sources (model memory) never win and
    are listed so the caller sees what was discarded.
    """
    subject = assertions[0].subject if assertions else ""
    scored = [
        (a, a.resolved_confidence(calibration))
        for a in assertions
        if a.source not in REFUSED_SOURCES
    ]
    refused = tuple(a.source for a in assertions if a.source in REFUSED_SOURCES)
    if not scored:
        return ArbitratedFact(
            subject=subject,
            value=None,
            confidence=0.0,
            source=None,
            conflict=False,
            refused=refused,
        )
    scored.sort(key=lambda pair: pair[1], reverse=True)
    winner, confidence = scored[0]
    conflict = any(
        other.value != winner.value and conf >= conflict_threshold for other, conf in scored[1:]
    )
    return ArbitratedFact(
        subject=subject,
        value=winner.value,
        confidence=confidence,
        source=winner.source,
        conflict=conflict,
        refused=refused,
    )


@dataclass
class ArbitrationReport:
    """Arbitrated facts across many subjects."""

    facts: list[ArbitratedFact] = field(default_factory=list)

    @property
    def conflicts(self) -> list[ArbitratedFact]:
        return [f for f in self.facts if f.conflict]

    def render(self) -> str:
        lines = ["# fact arbitration"]
        lines += [f.render().rstrip("\n") for f in self.facts]
        if self.conflicts:
            lines.append("")
            lines.append(f"{len(self.conflicts)} conflicting fact(s) need resolution")
        return "\n".join(lines) + "\n"


def arbitrate_all(
    grouped: dict[str, list[FactAssertion]], calibration: dict[str, float] | None = None
) -> ArbitrationReport:
    """Arbitrate each subject's assertions into a single report."""
    report = ArbitrationReport()
    for subject in sorted(grouped):
        report.facts.append(arbitrate(grouped[subject], calibration))
    return report
