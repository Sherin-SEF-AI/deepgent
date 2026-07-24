"""deepgent profile thermal: sustained thermal/DVFS performance envelope (#3).

Burst benchmarks overstate what a fanless edge board actually holds. This
profiler drives each nvpmodel power mode, runs a sustained workload, and
samples tegrastats in windows to separate burst throughput from the
thermally saturated sustained throughput, locating the thermal knee where the
board starts throttling. Analysis is deterministic; nothing is model-judged.

The board's original power mode is restored on exit, even after a failure, so
the profiler never leaves a target in a modified state (section 14).
"""

import asyncio
import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from statistics import median

import structlog

from deepgent.boards import BoardRunner, LocalRunner, get_board, open_runner
from deepgent.errors import BoardError

_Runner = BoardRunner | LocalRunner

_logger = structlog.get_logger(__name__)

_CAPTURE_INTERVAL_MS = 500
# A window whose peak tj comes within this margin of the ceiling is treated as
# thermally saturated (throttle onset).
_THERMAL_MARGIN_C = 2.0
# Throughput sustained below this fraction of burst counts as a real drop.
_SUSTAIN_RATIO = 0.9
_THROUGHPUT = re.compile(
    r"([\d.]+)\s*(?:fps|it/s|items/s)\b|\b(?:fps|throughput)\D*([\d.]+)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class PowerMode:
    """One nvpmodel power mode to profile."""

    id: int
    name: str


@dataclass(frozen=True)
class WindowSample:
    """Summary metrics for one sampling window within a mode."""

    t_s: float
    tj_c: float | None
    power_w: float | None
    gr3d_pct: float | None


@dataclass(frozen=True)
class ThroughputStats:
    """Burst vs sustained throughput derived from a periodic fps stream."""

    samples: int
    burst: float
    sustained: float

    @property
    def drop_pct(self) -> float:
        """Percent throughput lost from burst to sustained (>=0)."""
        if self.burst <= 0:
            return 0.0
        return max(0.0, (self.burst - self.sustained) / self.burst * 100.0)


@dataclass
class ModeEnvelope:
    """Sustained profile for one power mode."""

    mode: str
    windows: list[WindowSample] = field(default_factory=list)
    throughput: ThroughputStats | None = None
    tj_max_c: float | None = None
    power_mean_w: float | None = None
    throttled: bool = False
    knee_s: float | None = None
    note: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "mode": self.mode,
            "windows": len(self.windows),
            "tj_max_c": self.tj_max_c,
            "power_mean_w": self.power_mean_w,
            "throttled": self.throttled,
            "knee_s": self.knee_s,
            "burst_fps": None if self.throughput is None else self.throughput.burst,
            "sustained_fps": None if self.throughput is None else self.throughput.sustained,
            "drop_pct": None if self.throughput is None else self.throughput.drop_pct,
            "note": self.note,
        }


@dataclass
class ThermalEnvelopeResult:
    """All profiled modes plus rendered evidence."""

    board: str
    workload: str
    modes: list[ModeEnvelope] = field(default_factory=list)

    @property
    def best_mode(self) -> ModeEnvelope | None:
        """The power mode with the highest sustained throughput."""
        scored = [m for m in self.modes if m.throughput is not None]
        return max(scored, key=lambda m: m.throughput.sustained) if scored else None  # type: ignore[union-attr]

    def to_dict(self) -> dict[str, object]:
        return {
            "board": self.board,
            "workload": self.workload,
            "best_mode": None if self.best_mode is None else self.best_mode.mode,
            "modes": [mode.to_dict() for mode in self.modes],
        }

    def render_table(self) -> str:
        header = (
            f"{'mode':<14} {'burst_fps':>9} {'sust_fps':>9} {'drop%':>6} "
            f"{'tj_c':>6} {'power_w':>8} {'knee_s':>7} {'throttled':>9}"
        )
        rows = [header, "-" * len(header)]
        for mode in self.modes:
            tp = mode.throughput
            rows.append(
                f"{mode.mode:<14} "
                f"{_fmt(None if tp is None else tp.burst):>9} "
                f"{_fmt(None if tp is None else tp.sustained):>9} "
                f"{_fmt(None if tp is None else tp.drop_pct):>6} "
                f"{_fmt(mode.tj_max_c):>6} {_fmt(mode.power_mean_w):>8} "
                f"{_fmt(mode.knee_s):>7} {'yes' if mode.throttled else 'no':>9}"
            )
        if self.best_mode is not None:
            rows.append("-" * len(header))
            rows.append(f"best sustained throughput: {self.best_mode.mode}")
        return "\n".join(rows) + "\n"

    def persist(self, run_dir: Path) -> None:
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "thermal-envelope.json").write_text(json.dumps(self.to_dict(), indent=2))
        (run_dir / "thermal-envelope.txt").write_text(self.render_table())


def _fmt(value: float | None) -> str:
    return "-" if value is None else f"{value:.2f}"


def parse_throughput_series(text: str) -> list[float]:
    """Extract an ordered throughput (fps) series from workload stdout."""
    series: list[float] = []
    for match in _THROUGHPUT.finditer(text):
        token = match.group(1) or match.group(2)
        if token is None:
            continue
        try:
            series.append(float(token))
        except ValueError:  # pragma: no cover - regex guarantees numeric
            continue
    return series


def analyze_throughput(series: list[float]) -> ThroughputStats | None:
    """Burst (peak of the first third) vs sustained (median of the last third)."""
    if not series:
        return None
    third = max(1, len(series) // 3)
    burst = max(series[:third])
    sustained = median(series[-third:])
    return ThroughputStats(samples=len(series), burst=burst, sustained=sustained)


def analyze_mode(
    mode: str,
    windows: list[WindowSample],
    series: list[float],
    tj_ceiling_c: float,
    note: str | None = None,
) -> ModeEnvelope:
    """Pure envelope analysis for one mode (no hardware)."""
    envelope = ModeEnvelope(mode=mode, windows=list(windows), note=note)
    tjs = [w.tj_c for w in windows if w.tj_c is not None]
    if tjs:
        envelope.tj_max_c = max(tjs)
    powers = [w.power_w for w in windows if w.power_w is not None]
    if powers:
        envelope.power_mean_w = sum(powers) / len(powers)
    envelope.throughput = analyze_throughput(series)

    # Thermal knee: first window whose tj reaches within margin of the ceiling.
    for window in windows:
        if window.tj_c is not None and window.tj_c >= tj_ceiling_c - _THERMAL_MARGIN_C:
            envelope.throttled = True
            envelope.knee_s = window.t_s
            break
    # A sustained throughput drop below the ratio is also throttling evidence.
    if envelope.throughput is not None and envelope.throughput.burst > 0:
        ratio = envelope.throughput.sustained / envelope.throughput.burst
        if ratio < _SUSTAIN_RATIO:
            envelope.throttled = True
    return envelope


def parse_modes(spec: str) -> list[PowerMode]:
    """Parse a '0:MAXN,1:30W' mode spec into PowerMode entries."""
    modes: list[PowerMode] = []
    for entry in spec.split(","):
        entry = entry.strip()
        if not entry:
            continue
        parts = entry.split(":", 1)
        try:
            mode_id = int(parts[0])
        except ValueError as exc:
            raise BoardError(f"invalid power-mode id in '{entry}'; expected '<id>[:name]'") from exc
        name = parts[1] if len(parts) == 2 and parts[1] else f"mode-{mode_id}"
        modes.append(PowerMode(id=mode_id, name=name))
    if not modes:
        raise BoardError("no power modes parsed from spec")
    return modes


class ThermalEnvelopeProfiler:
    """Drives sustained-throughput profiling across power modes."""

    def __init__(self, board_id: str, run_dir: Path, window_s: float = 30.0) -> None:
        self._board_id = board_id
        self._run_dir = run_dir
        self._window_s = window_s

    async def run(
        self,
        workload: str,
        hold_s: float,
        modes: list[PowerMode] | None = None,
        tj_ceiling_c: float = 95.0,
    ) -> ThermalEnvelopeResult:
        """Profile the workload across modes; restore the original mode after."""
        board = get_board(self._board_id)
        result = ThermalEnvelopeResult(board=self._board_id, workload=workload)
        log = _logger.bind(board=self._board_id)

        async with open_runner(board) as runner:
            original = await self._current_mode(runner)
            try:
                for mode in modes or [PowerMode(id=-1, name="current")]:
                    note = await self._set_mode(runner, mode.id) if mode.id >= 0 else None
                    log.info("thermal_mode", mode=mode.name)
                    windows, series = await self._profile_once(runner, workload, hold_s)
                    result.modes.append(
                        analyze_mode(mode.name, windows, series, tj_ceiling_c, note)
                    )
                    self._run_dir.mkdir(parents=True, exist_ok=True)
                    (self._run_dir / f"{mode.name}-throughput.txt").write_text(
                        "\n".join(f"{s:.3f}" for s in series)
                    )
            finally:
                if original is not None:
                    await self._set_mode(runner, original)

        result.persist(self._run_dir)
        return result

    async def _profile_once(
        self, runner: _Runner, workload: str, hold_s: float
    ) -> tuple[list[WindowSample], list[float]]:
        workload_task = asyncio.create_task(runner.run(workload, timeout_s=hold_s + 30))
        windows: list[WindowSample] = []
        start = time.time()
        end = start + hold_s
        while time.time() < end:
            window = min(self._window_s, max(end - time.time(), 0.1))
            metrics = await runner.capture_metrics(window, _CAPTURE_INTERVAL_MS)
            windows.append(
                WindowSample(
                    t_s=time.time() - start,
                    tj_c=metrics.get("tj_max_c"),
                    power_w=metrics.get("power_mean_w"),
                    gr3d_pct=metrics.get("gr3d_mean_pct"),
                )
            )
        workload_result = await workload_task
        output = workload_result.stdout + workload_result.stderr
        return windows, parse_throughput_series(output)

    @staticmethod
    async def _current_mode(runner: _Runner) -> int | None:
        try:
            result = await runner.run("nvpmodel -q 2>/dev/null | tail -n1", timeout_s=15)
        except BoardError:
            return None
        text = result.stdout.strip()
        return int(text) if text.isdigit() else None

    @staticmethod
    async def _set_mode(runner: _Runner, mode_id: int) -> str | None:
        try:
            result = await runner.run(f"sudo nvpmodel -m {mode_id}", timeout_s=30)
        except BoardError as exc:
            return f"nvpmodel set failed: {exc}"
        if result.exit_status != 0:
            return f"nvpmodel -m {mode_id} exited {result.exit_status}"
        return None
