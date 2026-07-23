"""Thermal-envelope (#3) and glass-to-glass latency (#4) profiling.

Pure analysis is tested directly; the on-target paths use a board runner
double, so live hardware is never required (live runs are deferred to the
board runner workflow).
"""

import asyncio
from pathlib import Path
from typing import Any, ClassVar

import pytest

import deepgent.evals.latency_trace as latency_module
import deepgent.evals.thermal_envelope as thermal_module
from deepgent.boards import BoardConfig, CommandResult, add_board
from deepgent.errors import BoardError
from deepgent.evals.latency_trace import (
    LatencyTracer,
    analyze_trace,
    parse_stage_lines,
    percentile,
)
from deepgent.evals.thermal_envelope import (
    PowerMode,
    ThermalEnvelopeProfiler,
    WindowSample,
    analyze_mode,
    analyze_throughput,
    parse_modes,
    parse_throughput_series,
)

pytestmark = pytest.mark.unit


@pytest.fixture
def fake_board(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    (tmp_path / "home").mkdir()
    add_board(
        BoardConfig(
            id="agx-orin",
            host="198.51.100.10",
            ssh_user="nvidia",
            key_path=Path("~/.ssh/k"),
            type="jetson-agx-orin",
        )
    )


# --- Thermal envelope: pure analysis ---------------------------------------


def test_parse_throughput_series() -> None:
    text = "warmup\nfps 60.0\n30.5 fps\nthroughput: 29\ngarbage line\n"
    assert parse_throughput_series(text) == [60.0, 30.5, 29.0]


def test_analyze_throughput_burst_vs_sustained() -> None:
    series = [60.0, 59.0, 58.0, 50.0, 49.0, 48.0, 40.0, 39.0, 38.0]
    stats = analyze_throughput(series)
    assert stats is not None
    assert stats.burst == pytest.approx(60.0)
    assert stats.sustained == pytest.approx(39.0)
    assert stats.drop_pct == pytest.approx((60.0 - 39.0) / 60.0 * 100.0)


def test_analyze_throughput_empty() -> None:
    assert analyze_throughput([]) is None


def test_analyze_mode_flags_thermal_knee() -> None:
    windows = [
        WindowSample(t_s=0.0, tj_c=70.0, power_w=20.0, gr3d_pct=95.0),
        WindowSample(t_s=30.0, tj_c=94.0, power_w=30.0, gr3d_pct=80.0),
    ]
    env = analyze_mode("MAXN", windows, [30.0, 30.0, 30.0], tj_ceiling_c=95.0)
    assert env.throttled is True
    assert env.knee_s == pytest.approx(30.0)
    assert env.tj_max_c == pytest.approx(94.0)
    assert env.power_mean_w == pytest.approx(25.0)


def test_analyze_mode_not_throttled_when_cool_and_flat() -> None:
    windows = [WindowSample(t_s=0.0, tj_c=60.0, power_w=10.0, gr3d_pct=90.0)]
    env = analyze_mode("30W", windows, [30.0, 30.0, 30.0], tj_ceiling_c=95.0)
    assert env.throttled is False
    assert env.knee_s is None


def test_parse_modes() -> None:
    modes = parse_modes("0:MAXN, 1:30W ,2")
    assert modes == [
        PowerMode(0, "MAXN"),
        PowerMode(1, "30W"),
        PowerMode(2, "mode-2"),
    ]


def test_parse_modes_rejects_garbage() -> None:
    with pytest.raises(BoardError):
        parse_modes("notanumber")


# --- Thermal envelope: on-target path with a runner double -----------------


class _FakeThermalRunner:
    windows: ClassVar[list[dict[str, float]]] = []
    workload_out: ClassVar[str] = ""
    set_calls: ClassVar[list[int]] = []

    def __init__(self, board: BoardConfig) -> None:
        self._i = 0

    async def __aenter__(self) -> "_FakeThermalRunner":
        return self

    async def __aexit__(self, *args: Any) -> None:
        return None

    async def run(self, command: str, timeout_s: float = 60.0) -> CommandResult:
        if "nvpmodel -q" in command:
            return CommandResult(command, 0, "0\n", "", False)
        if "nvpmodel -m" in command:
            _FakeThermalRunner.set_calls.append(int(command.rsplit(" ", 1)[1]))
            return CommandResult(command, 0, "", "", False)
        return CommandResult(command, 0, _FakeThermalRunner.workload_out, "", False)

    async def capture_metrics(self, duration_s: float, interval_ms: int = 500) -> dict[str, float]:
        window = _FakeThermalRunner.windows[min(self._i, len(_FakeThermalRunner.windows) - 1)]
        self._i += 1
        return dict(window)


def test_thermal_profiler_end_to_end(
    fake_board: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _FakeThermalRunner.windows = [{"tj_max_c": 94.0, "power_mean_w": 30.0, "gr3d_mean_pct": 85.0}]
    _FakeThermalRunner.workload_out = "fps 60\nfps 59\nfps 58\nfps 40\nfps 39\nfps 38\n"
    _FakeThermalRunner.set_calls = []
    monkeypatch.setattr(thermal_module, "open_runner", lambda b: _FakeThermalRunner(b))

    run_dir = tmp_path / "run"
    profiler = ThermalEnvelopeProfiler("agx-orin", run_dir, window_s=1.0)
    result = asyncio.run(
        profiler.run("./bench", hold_s=0.02, modes=[PowerMode(0, "MAXN")], tj_ceiling_c=95.0)
    )
    assert len(result.modes) == 1
    mode = result.modes[0]
    assert mode.throttled is True
    assert mode.tj_max_c == pytest.approx(94.0)
    assert mode.throughput is not None and mode.throughput.burst == pytest.approx(60.0)
    # Mode set to 0, then original (0) restored.
    assert _FakeThermalRunner.set_calls[0] == 0
    assert (run_dir / "thermal-envelope.json").is_file()
    assert (run_dir / "thermal-envelope.txt").is_file()


# --- Latency trace: pure analysis ------------------------------------------


def test_percentile_interpolates() -> None:
    assert percentile([10.0], 99) == pytest.approx(10.0)
    assert percentile([0.0, 10.0], 50) == pytest.approx(5.0)
    assert percentile([1.0, 2.0, 3.0, 4.0], 50) == pytest.approx(2.5)


def test_parse_stage_lines_explicit_and_inferred_frames() -> None:
    text = (
        "STAGE capture 2.0 frame=0\n"
        "STAGE infer 8.0 frame=0\n"
        '{"stage": "capture", "ms": 3.0, "frame": 1}\n'
        '{"stage": "infer", "ms": 9.0, "frame": 1}\n'
    )
    timings = parse_stage_lines(text)
    assert len(timings) == 4
    assert timings[0].stage == "capture" and timings[0].frame == 0
    assert timings[3].stage == "infer" and timings[3].frame == 1


def test_parse_stage_lines_infers_frames_by_repeat() -> None:
    text = "STAGE a 1.0\nSTAGE b 2.0\nSTAGE a 1.5\nSTAGE b 2.5\n"
    timings = parse_stage_lines(text)
    frames = {t.frame for t in timings}
    assert frames == {0, 1}


def test_analyze_trace_bottleneck_and_budget() -> None:
    text = "\n".join(
        f"STAGE capture 2.0 frame={i}\nSTAGE infer 10.0 frame={i}\nSTAGE post 1.0 frame={i}"
        for i in range(100)
    )
    trace = analyze_trace(parse_stage_lines(text), budget_ms=15.0)
    assert trace.frames == 100
    assert trace.bottleneck is not None and trace.bottleneck.name == "infer"
    assert trace.g2g_p99 == pytest.approx(13.0)
    assert trace.passed is True
    tight = analyze_trace(parse_stage_lines(text), budget_ms=10.0)
    assert tight.passed is False


def test_analyze_trace_empty() -> None:
    trace = analyze_trace([], budget_ms=10.0)
    assert trace.frames == 0
    assert trace.bottleneck is None
    assert trace.passed is None


# --- Latency trace: on-target path with a runner double --------------------


class _FakeLatencyRunner:
    output: ClassVar[str] = ""
    exit_status: ClassVar[int] = 0

    def __init__(self, board: BoardConfig) -> None:
        pass

    async def __aenter__(self) -> "_FakeLatencyRunner":
        return self

    async def __aexit__(self, *args: Any) -> None:
        return None

    async def run(self, command: str, timeout_s: float = 60.0) -> CommandResult:
        return CommandResult(
            command, _FakeLatencyRunner.exit_status, _FakeLatencyRunner.output, "", False
        )


def test_latency_tracer_end_to_end(
    fake_board: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _FakeLatencyRunner.output = "STAGE capture 2.0 frame=0\nSTAGE infer 10.0 frame=0\n"
    _FakeLatencyRunner.exit_status = 0
    monkeypatch.setattr(latency_module, "open_runner", lambda b: _FakeLatencyRunner(b))

    run_dir = tmp_path / "run"
    tracer = LatencyTracer("agx-orin", run_dir)
    trace = asyncio.run(tracer.run("./pipeline", budget_ms=15.0, capture_s=1.0))
    assert trace.frames == 1
    assert trace.g2g_p99 == pytest.approx(12.0)
    assert (run_dir / "latency-trace.json").is_file()
    assert (run_dir / "pipeline-output.txt").is_file()


def test_latency_tracer_raises_on_pipeline_error(
    fake_board: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _FakeLatencyRunner.output = "boom"
    _FakeLatencyRunner.exit_status = 3
    monkeypatch.setattr(latency_module, "open_runner", lambda b: _FakeLatencyRunner(b))
    tracer = LatencyTracer("agx-orin", tmp_path / "run")
    with pytest.raises(BoardError):
        asyncio.run(tracer.run("./pipeline", capture_s=1.0))
