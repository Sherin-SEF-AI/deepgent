"""Empirically-validated skill lifecycle (#13).

Skills should earn their context budget. This measures each skill's causal
lift from ablation data - golden outcomes with the skill present versus absent
- and recommends promoting, keeping, or retiring it. Knowledge stops accreting
indiscriminately and starts competing on measured value; a skill that does not
raise pass-rate or cut loops is flagged for refinement or removal.

Pure functions over ablation records, so the lifecycle policy is unit-tested.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path

# Minimum lift (pass-rate delta) for a skill to justify its context.
_PROMOTE_LIFT = 0.15
_RETIRE_LIFT = 0.0
_MIN_SAMPLES = 4


@dataclass(frozen=True)
class AblationRecord:
    """One golden outcome, tagged with whether a skill was present."""

    skill: str
    present: bool
    passed: bool
    loops: int


@dataclass(frozen=True)
class SkillMetric:
    """Measured effect of one skill from ablation data."""

    skill: str
    samples_with: int
    samples_without: int
    pass_with: float
    pass_without: float
    loops_with: float
    loops_without: float

    @property
    def pass_lift(self) -> float:
        return self.pass_with - self.pass_without

    @property
    def loop_delta(self) -> float:
        """Negative means the skill reduced loop count (good)."""
        return self.loops_with - self.loops_without

    @property
    def has_data(self) -> bool:
        return self.samples_with >= _MIN_SAMPLES and self.samples_without >= _MIN_SAMPLES

    @property
    def verdict(self) -> str:
        if not self.has_data:
            return "insufficient-data"
        if self.pass_lift >= _PROMOTE_LIFT or (self.pass_lift >= 0 and self.loop_delta < -0.5):
            return "promote"
        if self.pass_lift <= _RETIRE_LIFT and self.loop_delta >= -0.5:
            return "retire"
        return "keep"

    def to_dict(self) -> dict[str, object]:
        return {
            "skill": self.skill,
            "samples_with": self.samples_with,
            "samples_without": self.samples_without,
            "pass_lift": self.pass_lift,
            "loop_delta": self.loop_delta,
            "verdict": self.verdict,
        }


def _rate(records: list[AblationRecord], present: bool) -> tuple[int, float, float]:
    subset = [r for r in records if r.present is present]
    if not subset:
        return 0, 0.0, 0.0
    passed = sum(1 for r in subset if r.passed) / len(subset)
    loops = sum(r.loops for r in subset) / len(subset)
    return len(subset), passed, loops


def evaluate_skills(records: list[AblationRecord]) -> list[SkillMetric]:
    """Compute per-skill lift metrics from ablation records."""
    skills = sorted({r.skill for r in records})
    metrics: list[SkillMetric] = []
    for skill in skills:
        rows = [r for r in records if r.skill == skill]
        n_with, pass_with, loops_with = _rate(rows, True)
        n_without, pass_without, loops_without = _rate(rows, False)
        metrics.append(
            SkillMetric(
                skill=skill,
                samples_with=n_with,
                samples_without=n_without,
                pass_with=pass_with,
                pass_without=pass_without,
                loops_with=loops_with,
                loops_without=loops_without,
            )
        )
    return metrics


@dataclass
class LifecycleReport:
    """Skill metrics plus the lifecycle recommendations."""

    metrics: list[SkillMetric] = field(default_factory=list)

    @property
    def to_retire(self) -> list[str]:
        return [m.skill for m in self.metrics if m.verdict == "retire"]

    def to_dict(self) -> dict[str, object]:
        return {"skills": [m.to_dict() for m in self.metrics], "to_retire": self.to_retire}

    def render(self) -> str:
        header = f"{'skill':<24} {'pass_lift':>9} {'loop_delta':>10} {'verdict':>16}"
        rows = ["# skill lifecycle", "", header, "-" * len(header)]
        for m in self.metrics:
            rows.append(
                f"{m.skill:<24} {m.pass_lift:>+9.2f} {m.loop_delta:>+10.1f} {m.verdict:>16}"
            )
        if self.to_retire:
            rows.append("")
            rows.append(f"retire candidates: {', '.join(self.to_retire)}")
        return "\n".join(rows) + "\n"


def analyze_lifecycle(records: list[AblationRecord]) -> LifecycleReport:
    """Full lifecycle pass over ablation records."""
    return LifecycleReport(metrics=evaluate_skills(records))


def load_ablation(data: str) -> list[AblationRecord]:
    """Parse an ablation JSON array: [{skill, present, passed, loops}]."""
    parsed = json.loads(data)
    return [
        AblationRecord(
            skill=str(item["skill"]),
            present=bool(item["present"]),
            passed=bool(item["passed"]),
            loops=int(item.get("loops", 0)),
        )
        for item in parsed
    ]


def load_ablation_file(path: Path) -> list[AblationRecord]:
    return load_ablation(path.read_text())
