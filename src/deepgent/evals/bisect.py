"""deepgent bisect: isolate the exact change that broke a golden (Tier 1).

Binary search over an ordered candidate list (git commits between a known
good and known bad ref, or container tag versions), re-running a golden as
the predicate at each probe. The predicate is the mechanical golden score,
so the procedure is fully deterministic; on-hardware goldens make it
hardware-truthful.

Invariant: candidates[0] is known good and candidates[-1] is known bad;
both endpoints are trusted, not re-tested. The result is the first bad
candidate (the breaking change) and the last good one before it.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

import structlog

from deepgent.errors import GoldenError

_logger = structlog.get_logger(__name__)

# A predicate returns True when the candidate is GOOD (golden passes).
Predicate = Callable[[str], Awaitable[bool]]


@dataclass(frozen=True)
class BisectStep:
    """One probe: which candidate was tested and whether it passed."""

    candidate: str
    passed: bool


@dataclass
class BisectResult:
    """Outcome of a bisect session."""

    candidates: list[str]
    steps: list[BisectStep] = field(default_factory=list)
    first_bad: str | None = None

    @property
    def last_good(self) -> str | None:
        if self.first_bad is None:
            return None
        index = self.candidates.index(self.first_bad)
        return self.candidates[index - 1] if index > 0 else None

    def render_report(self) -> str:
        lines = ["# bisect report", ""]
        for step in self.steps:
            lines.append(f"probe {step.candidate}: {'pass' if step.passed else 'FAIL'}")
        lines.append("")
        if self.first_bad is not None:
            lines.append(f"first bad: {self.first_bad}")
            if self.last_good is not None:
                lines.append(f"last good: {self.last_good}")
            lines.append(f"probes run: {len(self.steps)} over {len(self.candidates)} candidates")
        return "\n".join(lines) + "\n"


async def bisect(candidates: list[str], predicate: Predicate) -> BisectResult:
    """Find the first failing candidate in O(log n) predicate runs.

    Endpoints are trusted: candidates[0] good, candidates[-1] bad. Interior
    candidates are probed by binary search; the first bad candidate is the
    lowest index that fails. With only the two endpoints, the bad endpoint
    itself is the answer with zero probes.
    """
    if len(candidates) < 2:
        raise GoldenError("bisect needs at least a known-good and a known-bad candidate")
    result = BisectResult(candidates=list(candidates))
    # Invariant across the loop: `good` indexes a known-good candidate and
    # `bad` a known-bad one, with good < bad. Endpoints seed it untested.
    good = 0
    bad = len(candidates) - 1
    while bad - good > 1:
        mid = (good + bad) // 2
        candidate = candidates[mid]
        passed = await predicate(candidate)
        result.steps.append(BisectStep(candidate=candidate, passed=passed))
        _logger.info("bisect_probe", candidate=candidate, passed=passed)
        if passed:
            good = mid
        else:
            bad = mid
    result.first_bad = candidates[bad]
    _logger.info("bisect_result", first_bad=result.first_bad, last_good=candidates[good])
    return result
