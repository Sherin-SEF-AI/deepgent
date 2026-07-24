"""deepgent differential: run one artifact across multiple boards, compare.

Deploys the same local artifact to each named board, runs it, captures
tegrastats, and renders a comparison table of latency, power, energy, and
declared cost so hardware selection becomes evidence rather than opinion.

Each board's run is independent (its own lease is taken by the board-farm
path in production); here the runner is invoked directly and the comparison
is pure post-processing over the per-board metrics.
"""

import asyncio
import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

import structlog

from deepgent.boards import BoardConfig, get_board, open_runner
from deepgent.errors import BoardError

_logger = structlog.get_logger(__name__)

_CAPTURE_INTERVAL_MS = 500
_LATENCY = re.compile(r"(?i)\b(?:latency|p99|mean)\D*([\d.]+)\s*ms")


@dataclass(frozen=True)
class BoardRun:
    """One board's differential result."""

    board: str
    exit_status: int
    latency_ms: float | None
    metrics: dict[str, float]
    cost_usd: float | None = None

    @property
    def ok(self) -> bool:
        return self.exit_status == 0


@dataclass
class DifferentialResult:
    """All boards' runs plus the rendered comparison."""

    artifact: str
    runs: list[BoardRun] = field(default_factory=list)

    def best_by(self, metric: str, lower_is_better: bool = True) -> BoardRun | None:
        """The board with the best value for a metric among successful runs.

        metric is 'latency_ms', 'power_mean_w', 'energy_j', or 'cost_usd'.
        """

        def value(run: BoardRun) -> float | None:
            if metric == "latency_ms":
                return run.latency_ms
            if metric == "cost_usd":
                return run.cost_usd
            return run.metrics.get(metric)

        scored = [(run, value(run)) for run in self.runs if run.ok]
        eligible = [(run, v) for run, v in scored if v is not None]
        if not eligible:
            return None
        pick = min if lower_is_better else max
        return pick(eligible, key=lambda pair: pair[1])[0]

    @property
    def winners(self) -> dict[str, str | None]:
        """Best board per metric (lower is better for all of these)."""
        result: dict[str, str | None] = {}
        for metric in ("latency_ms", "power_mean_w", "energy_j", "cost_usd"):
            best = self.best_by(metric)
            result[metric] = best.board if best is not None else None
        return result

    def to_dict(self) -> dict[str, object]:
        return {
            "artifact": self.artifact,
            "winners": self.winners,
            "runs": [
                {
                    "board": run.board,
                    "exit_status": run.exit_status,
                    "latency_ms": run.latency_ms,
                    "power_mean_w": run.metrics.get("power_mean_w"),
                    "energy_j": run.metrics.get("energy_j"),
                    "tj_max_c": run.metrics.get("tj_max_c"),
                    "cost_usd": run.cost_usd,
                }
                for run in self.runs
            ],
        }

    def render_table(self) -> str:
        header = (
            f"{'board':<14} {'exit':>4} {'latency_ms':>11} {'power_w':>8} "
            f"{'energy_j':>9} {'tj_c':>6} {'cost_usd':>9}"
        )
        rows = [header, "-" * len(header)]
        for run in self.runs:
            rows.append(
                f"{run.board:<14} {run.exit_status:>4} "
                f"{_fmt(run.latency_ms):>11} "
                f"{_fmt(run.metrics.get('power_mean_w')):>8} "
                f"{_fmt(run.metrics.get('energy_j')):>9} "
                f"{_fmt(run.metrics.get('tj_max_c')):>6} "
                f"{_fmt(run.cost_usd):>9}"
            )
        winners = self.winners
        if any(winners.values()):
            rows.append("-" * len(header))
            labels = {
                "latency_ms": "fastest",
                "power_mean_w": "lowest power",
                "energy_j": "most efficient",
                "cost_usd": "cheapest",
            }
            for metric, label in labels.items():
                if winners.get(metric):
                    rows.append(f"{label}: {winners[metric]}")
        return "\n".join(rows) + "\n"


def _fmt(value: float | None) -> str:
    return "-" if value is None else f"{value:.2f}"


def parse_latency_ms(output: str) -> float | None:
    """Best-effort latency extraction from workload stdout."""
    match = _LATENCY.search(output)
    return float(match.group(1)) if match else None


async def _run_one_board(
    board: BoardConfig,
    local_artifact: Path,
    remote_path: str,
    run_command: str,
    capture_s: float,
    cost_usd: float | None,
) -> BoardRun:
    async with open_runner(board) as runner:
        await runner.run(f"mkdir -p {Path(remote_path).parent}", timeout_s=30)
        await runner.put(local_artifact, remote_path)
        await runner.run(f"chmod +x {remote_path}", timeout_s=30)

        async def workload() -> tuple[int, str]:
            result = await runner.run(run_command, timeout_s=capture_s)
            return result.exit_status, result.stdout + result.stderr

        capture_task = asyncio.create_task(runner.capture_metrics(capture_s, _CAPTURE_INTERVAL_MS))
        exit_status, output = await workload()
        metrics = await capture_task
        await runner.run(f"rm -f {remote_path}", timeout_s=30)

    return BoardRun(
        board=board.id,
        exit_status=exit_status,
        latency_ms=parse_latency_ms(output),
        metrics=metrics,
        cost_usd=cost_usd,
    )


class DifferentialRunner:
    """Runs one artifact across several boards and compares."""

    def __init__(self, project_root: Path) -> None:
        self._project_root = project_root

    async def run(
        self,
        local_artifact: Path,
        board_ids: list[str],
        run_command: str,
        remote_path: str = "/tmp/deepgent-diff/artifact",
        capture_s: float = 30.0,
        costs: dict[str, float] | None = None,
    ) -> DifferentialResult:
        if not local_artifact.is_file():
            raise BoardError(f"artifact {local_artifact} does not exist")
        costs = costs or {}
        result = DifferentialResult(artifact=local_artifact.name)
        # Boards run sequentially: each holds its own board a while and the
        # comparison does not benefit from contended concurrency.
        for board_id in board_ids:
            board = get_board(board_id)
            _logger.info("differential_board", board=board_id)
            run = await _run_one_board(
                board,
                local_artifact,
                remote_path,
                run_command,
                capture_s,
                costs.get(board_id),
            )
            result.runs.append(run)
        return result

    def persist(self, result: DifferentialResult, run_dir: Path) -> None:
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "differential.json").write_text(json.dumps(result.to_dict(), indent=2))
        (run_dir / "comparison.txt").write_text(result.render_table())


def stamp() -> float:
    return time.time()
