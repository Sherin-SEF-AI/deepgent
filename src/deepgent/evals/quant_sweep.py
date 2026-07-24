"""TensorRT quantization sweep to an on-target Pareto frontier (#1).

Sweeps precision x batch x device placement, builds and benchmarks each config
on the target, and reduces the results to a Pareto frontier over latency,
energy, and accuracy so the best config is evidence, not opinion. The command
template is formatted per config, so the actual engine build/benchmark stays
in a deterministic script; deepgent runs the grid and does the reasoning.
"""

import json
from dataclasses import dataclass, field
from itertools import product
from pathlib import Path

import structlog

from deepgent.boards import get_board, open_runner
from deepgent.evals.bench import BenchResult, run_benchmark_on

_logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class SweepConfig:
    """One point in the quantization grid."""

    precision: str
    batch: int
    device: str

    @property
    def label(self) -> str:
        return f"{self.precision}-b{self.batch}-{self.device}"

    def format(self, template: str) -> str:
        return template.format(precision=self.precision, batch=self.batch, device=self.device)


@dataclass(frozen=True)
class SweepPoint:
    """A benchmarked config with the signals the frontier reasons over."""

    config: SweepConfig
    ok: bool
    latency_ms: float | None
    fps: float | None
    energy_j: float | None
    power_w: float | None
    accuracy: float | None
    note: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "config": self.config.label,
            "ok": self.ok,
            "latency_ms": self.latency_ms,
            "fps": self.fps,
            "energy_j": self.energy_j,
            "power_w": self.power_w,
            "accuracy": self.accuracy,
            "note": self.note,
        }


def expand_grid(precisions: list[str], batches: list[int], devices: list[str]) -> list[SweepConfig]:
    """Cartesian product of the sweep axes."""
    return [
        SweepConfig(precision=p, batch=b, device=d)
        for p, b, d in product(precisions, batches, devices)
    ]


def _dominates(a: SweepPoint, b: SweepPoint) -> bool:
    """True if a Pareto-dominates b over the objectives both expose.

    Latency is always compared (lower better); energy (lower better) and
    accuracy (higher better) join only when both points report them.
    """
    if a.latency_ms is None or b.latency_ms is None:
        return False
    objectives: list[tuple[float, float, bool]] = [(a.latency_ms, b.latency_ms, False)]
    if a.energy_j is not None and b.energy_j is not None:
        objectives.append((a.energy_j, b.energy_j, False))
    if a.accuracy is not None and b.accuracy is not None:
        objectives.append((a.accuracy, b.accuracy, True))
    not_worse = True
    strictly_better = False
    for av, bv, higher_better in objectives:
        if higher_better:
            if av < bv:
                not_worse = False
            elif av > bv:
                strictly_better = True
        else:
            if av > bv:
                not_worse = False
            elif av < bv:
                strictly_better = True
    return not_worse and strictly_better


def pareto_frontier(points: list[SweepPoint]) -> list[SweepPoint]:
    """Non-dominated, successfully-benchmarked configs."""
    candidates = [p for p in points if p.ok and p.latency_ms is not None]
    frontier: list[SweepPoint] = []
    for point in candidates:
        if not any(_dominates(other, point) for other in candidates if other is not point):
            frontier.append(point)
    return frontier


def knee(frontier: list[SweepPoint]) -> SweepPoint | None:
    """The efficiency knee: the frontier config with the best fps-per-watt.

    Falls back to fps-per-(1/latency) when power is unavailable, so it always
    returns a point when the frontier is non-empty and has throughput data.
    """

    def efficiency(point: SweepPoint) -> float | None:
        if point.fps is None:
            return None
        if point.power_w and point.power_w > 0:
            return point.fps / point.power_w
        return point.fps

    scored = [(p, efficiency(p)) for p in frontier]
    eligible = [(p, e) for p, e in scored if e is not None]
    if not eligible:
        return None
    return max(eligible, key=lambda pair: pair[1])[0]


def select_best(
    frontier: list[SweepPoint],
    max_power_w: float | None = None,
    min_fps: float | None = None,
    min_accuracy: float | None = None,
) -> SweepPoint | None:
    """Lowest-latency frontier point meeting the optional constraints."""
    eligible = [
        p
        for p in frontier
        if (max_power_w is None or (p.power_w is not None and p.power_w <= max_power_w))
        and (min_fps is None or (p.fps is not None and p.fps >= min_fps))
        and (min_accuracy is None or (p.accuracy is not None and p.accuracy >= min_accuracy))
    ]
    if not eligible:
        return None
    return min(eligible, key=lambda p: p.latency_ms if p.latency_ms is not None else float("inf"))


@dataclass
class QuantSweepResult:
    """All swept points, the frontier, and the selected config."""

    points: list[SweepPoint] = field(default_factory=list)
    accuracy_metric: str | None = None

    @property
    def frontier(self) -> list[SweepPoint]:
        return pareto_frontier(self.points)

    def to_dict(self) -> dict[str, object]:
        frontier_labels = {p.config.label for p in self.frontier}
        return {
            "accuracy_metric": self.accuracy_metric,
            "points": [
                {**p.to_dict(), "on_frontier": p.config.label in frontier_labels}
                for p in self.points
            ],
            "frontier": [p.config.label for p in self.frontier],
        }

    def render_table(self) -> str:
        frontier_labels = {p.config.label for p in self.frontier}
        header = (
            f"{'config':<20} {'ok':>3} {'lat_ms':>8} {'fps':>7} {'energy_j':>9} "
            f"{'power_w':>8} {'acc':>7} {'pareto':>7}"
        )
        rows = [header, "-" * len(header)]
        for p in self.points:
            rows.append(
                f"{p.config.label:<20} {'y' if p.ok else 'n':>3} "
                f"{_fmt(p.latency_ms):>8} {_fmt(p.fps):>7} {_fmt(p.energy_j):>9} "
                f"{_fmt(p.power_w):>8} {_fmt(p.accuracy):>7} "
                f"{'yes' if p.config.label in frontier_labels else '':>7}"
            )
        return "\n".join(rows) + "\n"

    def persist(self, run_dir: Path) -> None:
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "quant-sweep.json").write_text(json.dumps(self.to_dict(), indent=2))
        (run_dir / "quant-sweep.txt").write_text(self.render_table())


def _point_from_bench(config: SweepConfig, bench: BenchResult, metric: str | None) -> SweepPoint:
    accuracy = bench.named.get(metric) if metric else None
    return SweepPoint(
        config=config,
        ok=bench.ok,
        latency_ms=bench.latency_ms,
        fps=bench.fps,
        energy_j=bench.energy_j,
        power_w=bench.power_mean_w,
        accuracy=accuracy,
        note=None if bench.ok else f"exit {bench.exit_status}",
    )


class QuantSweepRunner:
    """Runs a quantization grid on one target and builds the frontier."""

    def __init__(self, board_id: str, run_dir: Path) -> None:
        self._board_id = board_id
        self._run_dir = run_dir

    async def run(
        self,
        command_template: str,
        configs: list[SweepConfig],
        capture_s: float = 30.0,
        accuracy_metric: str | None = None,
    ) -> QuantSweepResult:
        board = get_board(self._board_id)
        result = QuantSweepResult(accuracy_metric=accuracy_metric)
        async with open_runner(board) as runner:
            for config in configs:
                command = config.format(command_template)
                _logger.info("quant_sweep_config", config=config.label)
                bench = await run_benchmark_on(runner, command, capture_s)
                result.points.append(_point_from_bench(config, bench, accuracy_metric))
        result.persist(self._run_dir)
        return result


def _fmt(value: float | None) -> str:
    return "-" if value is None else f"{value:.2f}"
