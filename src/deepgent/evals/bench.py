"""Shared on-target benchmark primitive for the model/perf features.

One place to run a benchmark command on a target, capture tegrastats over the
same window, and parse the common signals (latency, throughput, an optional
accuracy/metric value) out of its stdout. The quantization sweep (#1), the
accuracy gate (#2), and the power-budget model selector (#6) all build on
this so they score the same shape.

Parsers are deterministic and total: a missing signal is None, never a
fabricated number.
"""

import asyncio
import re
from dataclasses import dataclass

from deepgent.boards import BoardRunner, LocalRunner, get_board, open_runner
from deepgent.boards.tegrastats import energy_per_item

_Runner = BoardRunner | LocalRunner

_CAPTURE_INTERVAL_MS = 500
_LATENCY = re.compile(r"(?i)\b(?:latency|p99|mean)\D*([\d.]+)\s*ms")
_FPS = re.compile(r"(?i)([\d.]+)\s*fps\b|\bfps\D*([\d.]+)")
_METRIC = re.compile(r"(?i)^\s*METRIC\s+(\S+)\s+([\d.]+)\s*$", re.MULTILINE)


@dataclass(frozen=True)
class BenchResult:
    """One benchmark run's parsed signals plus captured metrics."""

    command: str
    exit_status: int
    latency_ms: float | None
    fps: float | None
    metrics: dict[str, float]
    named: dict[str, float]

    @property
    def ok(self) -> bool:
        return self.exit_status == 0

    @property
    def power_mean_w(self) -> float | None:
        return self.metrics.get("power_mean_w")

    @property
    def energy_j(self) -> float | None:
        return self.metrics.get("energy_j")

    def energy_per_inference_j(self, items: int) -> float | None:
        return energy_per_item(self.metrics, items)


def parse_latency_ms(output: str) -> float | None:
    """Best-effort latency (ms) from workload stdout."""
    match = _LATENCY.search(output)
    return float(match.group(1)) if match else None


def parse_fps(output: str) -> float | None:
    """Best-effort throughput (fps) from workload stdout."""
    match = _FPS.search(output)
    if match is None:
        return None
    token = match.group(1) or match.group(2)
    return float(token) if token is not None else None


def parse_named_metrics(output: str) -> dict[str, float]:
    """Parse 'METRIC <name> <value>' lines into a mapping (e.g. mAP, top1)."""
    return {name: float(value) for name, value in _METRIC.findall(output)}


async def run_benchmark(board_id: str, command: str, capture_s: float = 30.0) -> BenchResult:
    """Run a benchmark command on a target and parse its signals."""
    board = get_board(board_id)
    async with open_runner(board) as runner:
        return await run_benchmark_on(runner, command, capture_s)


async def run_benchmark_on(runner: _Runner, command: str, capture_s: float = 30.0) -> BenchResult:
    """Run a benchmark on an already-open runner (used when a lease is held)."""
    capture_task = asyncio.create_task(runner.capture_metrics(capture_s, _CAPTURE_INTERVAL_MS))
    result = await runner.run(command, timeout_s=capture_s)
    metrics = await capture_task
    output = result.stdout + result.stderr
    return BenchResult(
        command=command,
        exit_status=result.exit_status,
        latency_ms=parse_latency_ms(output),
        fps=parse_fps(output),
        metrics=metrics,
        named=parse_named_metrics(output),
    )
