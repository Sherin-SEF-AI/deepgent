"""deepgent profile latency: glass-to-glass pipeline latency tracer (#4).

Latency is the metric AV pipelines live and die by, and the actionable number
is the per-stage breakdown, not a single end-to-end figure. This tracer runs
an instrumented pipeline that emits per-frame, per-stage timings, parses them
into per-stage latency distributions and per-frame glass-to-glass totals,
names the bottleneck stage, and gates the p99 total against a budget.

Instrumentation contract (either form, mixed freely):
  STAGE <name> <ms> [frame=<n>]        # plain line
  {"stage": "<name>", "ms": <float>, "frame": <n>}   # JSON line

Frames are grouped by an explicit ``frame`` field when present; otherwise a
new frame is inferred each time a stage name repeats. Analysis is
deterministic; a pipeline that emits no stage lines yields an empty trace,
never a fabricated number.
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from statistics import pstdev

import structlog

from deepgent.boards import get_board, open_runner
from deepgent.errors import BoardError

_logger = structlog.get_logger(__name__)

_STAGE_LINE = re.compile(r"^\s*STAGE\s+(\S+)\s+([\d.]+)\s*(?:frame=(\d+))?\s*$")


@dataclass(frozen=True)
class StageTiming:
    """One stage measurement within one frame."""

    stage: str
    ms: float
    frame: int


@dataclass(frozen=True)
class StageLatency:
    """Latency distribution for one pipeline stage."""

    name: str
    count: int
    p50: float
    p95: float
    p99: float
    mean: float
    max: float
    min: float = 0.0
    jitter: float = 0.0  # population standard deviation of the stage's samples

    @property
    def tail_ratio(self) -> float:
        """p99/p50: how much worse the tail is than the median (>=1)."""
        return self.p99 / self.p50 if self.p50 > 0 else 1.0


@dataclass
class LatencyTrace:
    """Per-stage distributions plus glass-to-glass totals."""

    stages: list[StageLatency] = field(default_factory=list)
    frames: int = 0
    g2g_p50: float | None = None
    g2g_p95: float | None = None
    g2g_p99: float | None = None
    g2g_jitter: float | None = None
    budget_ms: float | None = None

    @property
    def bottleneck(self) -> StageLatency | None:
        """The stage with the highest p99 (where to optimize first)."""
        return max(self.stages, key=lambda s: s.p99) if self.stages else None

    @property
    def passed(self) -> bool | None:
        """Whether p99 glass-to-glass meets the budget (None if no budget)."""
        if self.budget_ms is None or self.g2g_p99 is None:
            return None
        return self.g2g_p99 <= self.budget_ms

    def to_dict(self) -> dict[str, object]:
        return {
            "frames": self.frames,
            "budget_ms": self.budget_ms,
            "glass_to_glass": {
                "p50": self.g2g_p50,
                "p95": self.g2g_p95,
                "p99": self.g2g_p99,
                "jitter": self.g2g_jitter,
            },
            "passed": self.passed,
            "bottleneck": None if self.bottleneck is None else self.bottleneck.name,
            "stages": [
                {
                    "name": s.name,
                    "count": s.count,
                    "p50": s.p50,
                    "p95": s.p95,
                    "p99": s.p99,
                    "mean": s.mean,
                    "max": s.max,
                    "min": s.min,
                    "jitter": s.jitter,
                    "tail_ratio": s.tail_ratio,
                }
                for s in self.stages
            ],
        }

    def render_report(self) -> str:
        header = f"{'stage':<18} {'n':>5} {'p50':>7} {'p95':>7} {'p99':>7} {'jitter':>7} {'max':>7}"
        rows = [
            "# glass-to-glass latency trace",
            "",
            f"frames: {self.frames}",
            "",
            header,
            "-" * len(header),
        ]
        for s in self.stages:
            marker = "  <- bottleneck" if self.bottleneck is s else ""
            rows.append(
                f"{s.name:<18} {s.count:>5} {s.p50:>7.2f} {s.p95:>7.2f} "
                f"{s.p99:>7.2f} {s.jitter:>7.2f} {s.max:>7.2f}{marker}"
            )
        rows.append("-" * len(header))
        rows.append(
            f"glass-to-glass p50/p95/p99 ms: "
            f"{_fmt(self.g2g_p50)} / {_fmt(self.g2g_p95)} / {_fmt(self.g2g_p99)}"
            f"  (jitter {_fmt(self.g2g_jitter)})"
        )
        if self.budget_ms is not None:
            verdict = "PASS" if self.passed else "FAIL"
            rows.append(f"budget: {self.budget_ms:.2f} ms  ->  {verdict}")
        return "\n".join(rows) + "\n"

    def persist(self, run_dir: Path) -> None:
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "latency-trace.json").write_text(json.dumps(self.to_dict(), indent=2))
        (run_dir / "latency-trace.txt").write_text(self.render_report())


def _fmt(value: float | None) -> str:
    return "-" if value is None else f"{value:.2f}"


def percentile(values: list[float], q: float) -> float:
    """Linear-interpolated percentile (q in [0, 100]) over unsorted values."""
    if not values:
        raise ValueError("percentile of empty sequence")
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (q / 100.0) * (len(ordered) - 1)
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    frac = rank - low
    return ordered[low] + (ordered[high] - ordered[low]) * frac


def parse_stage_lines(text: str) -> list[StageTiming]:
    """Parse STAGE / JSON stage lines, inferring frame ids where absent."""
    timings: list[StageTiming] = []
    seen_in_frame: set[str] = set()
    inferred_frame = 0
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        stage: str | None = None
        ms: float | None = None
        explicit_frame: int | None = None

        match = _STAGE_LINE.match(line)
        if match:
            stage = match.group(1)
            ms = float(match.group(2))
            explicit_frame = int(match.group(3)) if match.group(3) else None
        elif line.startswith("{"):
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(obj, dict) or "stage" not in obj or "ms" not in obj:
                continue
            stage = str(obj["stage"])
            try:
                ms = float(obj["ms"])
            except (TypeError, ValueError):
                continue
            explicit_frame = int(obj["frame"]) if "frame" in obj else None
        if stage is None or ms is None:
            continue

        if explicit_frame is not None:
            frame = explicit_frame
        else:
            if stage in seen_in_frame:
                inferred_frame += 1
                seen_in_frame = set()
            seen_in_frame.add(stage)
            frame = inferred_frame
        timings.append(StageTiming(stage=stage, ms=ms, frame=frame))
    return timings


def analyze_trace(timings: list[StageTiming], budget_ms: float | None = None) -> LatencyTrace:
    """Build per-stage distributions and per-frame glass-to-glass totals."""
    trace = LatencyTrace(budget_ms=budget_ms)
    if not timings:
        return trace

    # Per-stage distributions, stages ordered by first appearance.
    order: list[str] = []
    by_stage: dict[str, list[float]] = {}
    for t in timings:
        if t.stage not in by_stage:
            by_stage[t.stage] = []
            order.append(t.stage)
        by_stage[t.stage].append(t.ms)
    for name in order:
        samples = by_stage[name]
        trace.stages.append(
            StageLatency(
                name=name,
                count=len(samples),
                p50=percentile(samples, 50),
                p95=percentile(samples, 95),
                p99=percentile(samples, 99),
                mean=sum(samples) / len(samples),
                max=max(samples),
                min=min(samples),
                jitter=pstdev(samples) if len(samples) > 1 else 0.0,
            )
        )

    # Per-frame glass-to-glass total = sum of that frame's stage timings.
    by_frame: dict[int, float] = {}
    for t in timings:
        by_frame[t.frame] = by_frame.get(t.frame, 0.0) + t.ms
    totals = list(by_frame.values())
    trace.frames = len(totals)
    trace.g2g_p50 = percentile(totals, 50)
    trace.g2g_p95 = percentile(totals, 95)
    trace.g2g_p99 = percentile(totals, 99)
    trace.g2g_jitter = pstdev(totals) if len(totals) > 1 else 0.0
    return trace


class LatencyTracer:
    """Runs an instrumented pipeline on-target and traces its latency."""

    def __init__(self, board_id: str, run_dir: Path) -> None:
        self._board_id = board_id
        self._run_dir = run_dir

    async def run(
        self, command: str, budget_ms: float | None = None, capture_s: float = 30.0
    ) -> LatencyTrace:
        board = get_board(self._board_id)
        _logger.info("latency_trace", board=self._board_id, budget_ms=budget_ms)
        async with open_runner(board) as runner:
            result = await runner.run(command, timeout_s=capture_s)
        output = result.stdout + result.stderr
        if result.exit_status != 0 and not result.timed_out:
            raise BoardError(
                f"pipeline exited {result.exit_status} on '{self._board_id}': "
                f"{result.stderr.strip()[:400]}"
            )
        self._run_dir.mkdir(parents=True, exist_ok=True)
        (self._run_dir / "pipeline-output.txt").write_text(output)
        trace = analyze_trace(parse_stage_lines(output), budget_ms)
        trace.persist(self._run_dir)
        return trace
