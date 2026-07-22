"""Golden task execution: dispatch, run directories, scoring, persistence."""

import json
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import structlog

from deepgent.errors import GoldenError
from deepgent.evals.gt0001 import run_gt_0001
from deepgent.evals.schema import CriterionResult, GoldenTask, load_golden, score

_logger = structlog.get_logger(__name__)

GOLDEN_DIR_NAME = "golden"
RUNS_RELPATH = Path(".deepgent") / "runs"
BASELINES_FILE = "baselines.json"

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


def baselines_path(project_root: Path) -> Path:
    return project_root / GOLDEN_DIR_NAME / BASELINES_FILE


def load_baselines(project_root: Path) -> dict[str, Any]:
    path = baselines_path(project_root)
    if not path.is_file():
        return {}
    data: dict[str, Any] = json.loads(path.read_text())
    return data


def update_baseline(result: GoldenRunResult, project_root: Path) -> None:
    """Record this run as the golden's regression baseline."""
    baselines = load_baselines(project_root)
    baselines[result.task.id] = {
        "passed": result.passed,
        "metrics": result.metrics,
    }
    baselines_path(project_root).write_text(json.dumps(baselines, indent=2, sort_keys=True))


def diff_against_baseline(result: GoldenRunResult, project_root: Path) -> list[str]:
    """Regression findings vs the stored baseline (docs/evals.md gate).

    A previously passing golden that now fails is always a regression; a
    passing run whose cost-like metrics (wall_s, loop-count style) degrade
    more than 15% is flagged for justification.
    """
    baselines = load_baselines(project_root)
    baseline = baselines.get(result.task.id)
    if baseline is None:
        return [f"no baseline recorded for {result.task.id}; run with --update-baseline"]
    findings: list[str] = []
    if baseline["passed"] and not result.passed:
        findings.append(f"regression: {result.task.id} previously passed and now fails")
    for metric in ("wall_s", "loop_count"):
        before = baseline["metrics"].get(metric)
        after = result.metrics.get(metric)
        if before and after and before > 0 and (after - before) / before > 0.15:
            findings.append(
                f"regression: {metric} degraded {((after - before) / before):.0%} "
                f"({before:g} -> {after:g}) without a justification label"
            )
    return findings
