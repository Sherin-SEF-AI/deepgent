"""Golden task runner, mechanical scoring, and the regression gate."""

from deepgent.evals.runner import GoldenRunResult, create_run_dir, find_golden_file, run_golden
from deepgent.evals.schema import (
    CriterionResult,
    GoldenTask,
    SuccessCriterion,
    load_golden,
    score,
)

__all__ = [
    "CriterionResult",
    "GoldenRunResult",
    "GoldenTask",
    "SuccessCriterion",
    "create_run_dir",
    "find_golden_file",
    "load_golden",
    "run_golden",
    "score",
]
