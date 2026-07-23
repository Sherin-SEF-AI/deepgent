"""Nsight bottleneck profiler (#10) and CUDA compute-sanitizer gate (#5).

Analysis and parsing are tested directly; on-target paths use a runner double
so live GPU hardware is never required.
"""

import asyncio
from pathlib import Path
from typing import Any, ClassVar

import pytest

import deepgent.evals.cuda_check as cuda_module
import deepgent.evals.nsight as nsight_module
from deepgent.boards import BoardConfig, CommandResult, add_board
from deepgent.errors import BoardError
from deepgent.evals.cuda_check import (
    CudaSanitizerRunner,
    parse_sanitizer_report,
    sanitizer_command,
)
from deepgent.evals.nsight import (
    NsightProfiler,
    NsightStats,
    classify_bottleneck,
    parse_nsight_report,
)
from deepgent.hooks.cuda_gate import is_cuda_file, make_cuda_gate

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


# --- Nsight -----------------------------------------------------------------


def test_parse_nsight_report() -> None:
    text = (
        "NSIGHT kernel_ns 8000\n"
        "NSIGHT memcpy_htod_ns 500\n"
        "NSIGHT memcpy_dtoh_ns 500\n"
        "NSIGHT sync_ns 1000\n"
        "NSIGHT kernel conv2d 6000 10\n"
        "noise\n"
    )
    stats = parse_nsight_report(text)
    assert stats.kernel_ns == 8000
    assert stats.memcpy_ns == 1000
    assert stats.sync_ns == 1000
    assert stats.kernels[0].name == "conv2d" and stats.kernels[0].instances == 10


def test_classify_compute_bound() -> None:
    stats = NsightStats(kernel_ns=9000, memcpy_htod_ns=200, sync_ns=800)
    report = classify_bottleneck(stats)
    assert report.kind == "compute_bound"
    assert report.breakdown["kernel"] > 50


def test_classify_memory_bound() -> None:
    stats = NsightStats(kernel_ns=1000, memcpy_htod_ns=5000, memcpy_dtoh_ns=3000, sync_ns=1000)
    report = classify_bottleneck(stats)
    assert report.kind == "memory_bound"


def test_classify_sync_bound() -> None:
    stats = NsightStats(kernel_ns=1000, sync_ns=6000, cpu_ns=1000)
    assert classify_bottleneck(stats).kind == "sync_bound"


def test_classify_balanced() -> None:
    stats = NsightStats(kernel_ns=100, memcpy_htod_ns=100, sync_ns=100, cpu_ns=100)
    assert classify_bottleneck(stats).kind == "balanced"


def test_classify_unknown_when_empty() -> None:
    assert classify_bottleneck(NsightStats()).kind == "unknown"


class _FakeNsightRunner:
    output: ClassVar[str] = ""

    def __init__(self, board: BoardConfig) -> None:
        pass

    async def __aenter__(self) -> "_FakeNsightRunner":
        return self

    async def __aexit__(self, *args: Any) -> None:
        return None

    async def run(self, command: str, timeout_s: float = 60.0) -> CommandResult:
        return CommandResult(command, 0, _FakeNsightRunner.output, "", False)


def test_nsight_profiler_end_to_end(
    fake_board: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _FakeNsightRunner.output = "NSIGHT kernel_ns 9000\nNSIGHT sync_ns 1000\n"
    monkeypatch.setattr(nsight_module, "open_runner", lambda b: _FakeNsightRunner(b))
    result = asyncio.run(NsightProfiler("agx-orin", tmp_path / "run").run("nsys-wrap", 1.0))
    assert result.report.kind == "compute_bound"
    assert (tmp_path / "run" / "nsight.json").is_file()


# --- CUDA sanitizer gate ----------------------------------------------------


def test_sanitizer_command() -> None:
    assert sanitizer_command("memcheck", "./app") == "compute-sanitizer --tool memcheck ./app"


def test_parse_memcheck_report() -> None:
    report = (
        "========= COMPUTE-SANITIZER\n"
        "========= Invalid __global__ read of size 4 bytes\n"
        "=========     at 0x70 in kernel(int*)\n"
        "========= ERROR SUMMARY: 1 error\n"
    )
    errors, count = parse_sanitizer_report("memcheck", report)
    assert count == 1
    assert len(errors) == 1 and "Invalid __global__ read" in errors[0].detail


def test_parse_clean_report() -> None:
    errors, count = parse_sanitizer_report("memcheck", "========= ERROR SUMMARY: 0 errors\n")
    assert errors == [] and count == 0


def test_parse_racecheck_hazards() -> None:
    report = (
        "========= Race reported between Write and Read\n"
        "========= RACECHECK SUMMARY: 2 hazards displayed\n"
    )
    errors, count = parse_sanitizer_report("racecheck", report)
    assert count == 2 and len(errors) == 1


class _FakeCudaRunner:
    outputs: ClassVar[dict[str, str]] = {}
    build_exit: ClassVar[int] = 0

    def __init__(self, board: BoardConfig) -> None:
        pass

    async def __aenter__(self) -> "_FakeCudaRunner":
        return self

    async def __aexit__(self, *args: Any) -> None:
        return None

    async def run(self, command: str, timeout_s: float = 60.0) -> CommandResult:
        if command.startswith("make") or "nvcc" in command:
            return CommandResult(command, _FakeCudaRunner.build_exit, "built", "", False)
        for key, out in _FakeCudaRunner.outputs.items():
            if f"--tool {key}" in command:
                return CommandResult(command, 0, out, "", False)
        return CommandResult(command, 0, "", "", False)


def test_cuda_check_clean(
    fake_board: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _FakeCudaRunner.build_exit = 0
    _FakeCudaRunner.outputs = {
        "memcheck": "========= ERROR SUMMARY: 0 errors\n",
        "racecheck": "========= RACECHECK SUMMARY: 0 hazards displayed\n",
    }
    monkeypatch.setattr(cuda_module, "open_runner", lambda b: _FakeCudaRunner(b))
    runner = CudaSanitizerRunner("agx-orin", tmp_path / "run")
    result = asyncio.run(runner.run("./app", "make", ["memcheck", "racecheck"]))
    assert result.clean is True
    assert (tmp_path / "run" / "cuda-check.json").is_file()


def test_cuda_check_flags_errors(
    fake_board: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _FakeCudaRunner.build_exit = 0
    _FakeCudaRunner.outputs = {
        "memcheck": "========= Invalid __global__ write\n========= ERROR SUMMARY: 1 error\n",
    }
    monkeypatch.setattr(cuda_module, "open_runner", lambda b: _FakeCudaRunner(b))
    runner = CudaSanitizerRunner("agx-orin", tmp_path / "run")
    result = asyncio.run(runner.run("./app", None, ["memcheck"]))
    assert result.clean is False
    assert result.summaries["memcheck"] == 1


def test_cuda_check_build_failure_raises(
    fake_board: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _FakeCudaRunner.build_exit = 2
    _FakeCudaRunner.outputs = {}
    monkeypatch.setattr(cuda_module, "open_runner", lambda b: _FakeCudaRunner(b))
    runner = CudaSanitizerRunner("agx-orin", tmp_path / "run")
    with pytest.raises(BoardError):
        asyncio.run(runner.run("./app", "make", ["memcheck"]))


def test_cuda_check_rejects_unknown_tool(
    fake_board: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cuda_module, "open_runner", lambda b: _FakeCudaRunner(b))
    runner = CudaSanitizerRunner("agx-orin", tmp_path / "run")
    with pytest.raises(BoardError):
        asyncio.run(runner.run("./app", None, ["bogus"]))


# --- cuda_gate hook ---------------------------------------------------------


def test_is_cuda_file() -> None:
    assert is_cuda_file("kernels/reduce.cu")
    assert is_cuda_file("include/util.cuh")
    assert not is_cuda_file("main.cpp")


def test_cuda_gate_advises_on_cu_write() -> None:
    gate = make_cuda_gate()
    output = asyncio.run(
        gate(
            {"tool_name": "Write", "tool_input": {"file_path": "k.cu"}, "cwd": "/x"},
            None,
            None,  # type: ignore[arg-type]
        )
    )
    assert "compute-sanitizer" in output.get("systemMessage", "")


def test_cuda_gate_ignores_non_cuda() -> None:
    gate = make_cuda_gate()
    output = asyncio.run(
        gate(
            {"tool_name": "Write", "tool_input": {"file_path": "main.cpp"}, "cwd": "/x"},
            None,
            None,  # type: ignore[arg-type]
        )
    )
    assert output == {}
