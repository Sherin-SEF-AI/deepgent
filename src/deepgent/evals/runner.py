"""Golden task execution: dispatch, run directories, scoring, persistence."""

import json
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path

import structlog

from deepgent.errors import GoldenError
from deepgent.evals.gt0001 import run_gt_0001
from deepgent.evals.schema import CriterionResult, GoldenTask, load_golden, score

_logger = structlog.get_logger(__name__)

GOLDEN_DIR_NAME = "golden"
RUNS_RELPATH = Path(".deepgent") / "runs"

GoldenImpl = Callable[[GoldenTask, Path], Awaitable[dict[str, float]]]

# Deterministic implementations by task class. Agent-driven goldens arrive
# with the board-farm MCP (Phase 2).
IMPLEMENTATIONS: dict[str, GoldenImpl] = {
    "bringup/cuda-smoke": run_gt_0001,
}


@dataclass(frozen=True)
class GoldenRunResult:
    """Outcome of one golden run."""

    task: GoldenTask
    run_dir: Path
    metrics: dict[str, float]
    criteria: list[CriterionResult]

    @property
    def passed(self) -> bool:
        return all(criterion.passed for criterion in self.criteria)


def find_golden_file(task_id: str, project_root: Path) -> Path:
    return project_root / GOLDEN_DIR_NAME / f"{task_id}.yaml"


def create_run_dir(task_id: str, project_root: Path) -> Path:
    """Create .deepgent/runs/<task_id>-<utc timestamp>/ for artifacts."""
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    run_dir = project_root / RUNS_RELPATH / f"{task_id}-{stamp}"
    run_dir.mkdir(parents=True, exist_ok=False)
    return run_dir


async def run_golden(task_id: str, project_root: Path) -> GoldenRunResult:
    """Run one golden task, score it, and persist artifacts and results."""
    task = load_golden(find_golden_file(task_id, project_root))
    impl = IMPLEMENTATIONS.get(task.task_class)
    if impl is None:
        available = ", ".join(sorted(IMPLEMENTATIONS)) or "none"
        raise GoldenError(
            f"no implementation for golden class '{task.task_class}' (available: {available})"
        )

    run_dir = create_run_dir(task_id, project_root)
    log = _logger.bind(golden=task.id, run_dir=str(run_dir))
    log.info("golden_started", task_class=task.task_class, board=task.board)

    metrics = await impl(task, run_dir)
    criteria = score(metrics, task.success)
    result = GoldenRunResult(task=task, run_dir=run_dir, metrics=metrics, criteria=criteria)

    (run_dir / "metrics.json").write_text(json.dumps(metrics, indent=2, sort_keys=True))
    (run_dir / "result.json").write_text(
        json.dumps(
            {
                "id": task.id,
                "passed": result.passed,
                "criteria": [criterion.describe() for criterion in criteria],
            },
            indent=2,
        )
    )
    log.info("golden_finished", passed=result.passed)
    return result
