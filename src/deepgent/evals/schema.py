"""Golden task schema and mechanical scoring (section 17). No LLM judging."""

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, ValidationError

from deepgent.errors import GoldenError

Op = Literal[">=", "<=", "==", "!=", ">", "<"]


class SuccessCriterion(BaseModel):
    """One mechanical pass/fail check against a captured metric."""

    metric: str
    op: Op
    value: float


class GoldenTask(BaseModel):
    """A golden task definition, loaded from golden/<id>.yaml."""

    id: str
    title: str
    task_class: str = Field(alias="class")
    board: str
    skills: list[str] = Field(default_factory=list)
    inputs: dict[str, str] = Field(default_factory=dict)
    success: list[SuccessCriterion]
    budget_usd: float
    timeout_min: float

    model_config = {"populate_by_name": True}


def load_golden(path: Path) -> GoldenTask:
    """Load and validate one golden task YAML."""
    if not path.is_file():
        raise GoldenError(f"golden task file {path} does not exist")
    try:
        raw = yaml.safe_load(path.read_text())
    except yaml.YAMLError as exc:
        raise GoldenError(f"invalid YAML in {path}: {exc}") from exc
    try:
        return GoldenTask.model_validate(raw)
    except ValidationError as exc:
        raise GoldenError(f"invalid golden task in {path}: {exc}") from exc


@dataclass(frozen=True)
class CriterionResult:
    """Outcome of one success criterion."""

    metric: str
    op: Op
    expected: float
    actual: float | None
    passed: bool

    def describe(self) -> str:
        actual = "missing" if self.actual is None else f"{self.actual:g}"
        status = "pass" if self.passed else "FAIL"
        return f"{status}: {self.metric} {self.op} {self.expected:g} (actual: {actual})"


_OPS = {
    ">=": lambda a, b: a >= b,
    "<=": lambda a, b: a <= b,
    "==": lambda a, b: a == b,
    "!=": lambda a, b: a != b,
    ">": lambda a, b: a > b,
    "<": lambda a, b: a < b,
}


def score(metrics: dict[str, float], criteria: list[SuccessCriterion]) -> list[CriterionResult]:
    """Evaluate criteria against captured metrics; missing metrics fail."""
    results = []
    for criterion in criteria:
        actual = metrics.get(criterion.metric)
        passed = actual is not None and _OPS[criterion.op](actual, criterion.value)
        results.append(
            CriterionResult(
                metric=criterion.metric,
                op=criterion.op,
                expected=criterion.value,
                actual=actual,
                passed=passed,
            )
        )
    return results
