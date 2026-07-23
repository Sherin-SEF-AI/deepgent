"""'Why is it slow' profiler over an Nsight Systems trace (#10).

Runs the workload under nsys on the target, reads a normalized timing summary,
classifies the dominant bottleneck (compute / memory-copy / sync / CPU), and
emits concrete, deterministic recommendations. Raw fps tells you a pipeline is
slow; this tells you why and what to change.

Normalized summary contract (the on-board nsys wrapper emits these from
`nsys stats`, one per line; missing signals are simply absent):
  NSIGHT kernel_ns <n>
  NSIGHT memcpy_htod_ns <n>
  NSIGHT memcpy_dtoh_ns <n>
  NSIGHT sync_ns <n>
  NSIGHT cpu_ns <n>
  NSIGHT kernel <name> <time_ns> <instances>
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import structlog

from deepgent.boards import get_board, open_runner

_logger = structlog.get_logger(__name__)

_SCALAR = re.compile(
    r"^\s*NSIGHT\s+(kernel_ns|memcpy_htod_ns|memcpy_dtoh_ns|sync_ns|cpu_ns)\s+(\d+)"
)
_KERNEL = re.compile(r"^\s*NSIGHT\s+kernel\s+(\S+)\s+(\d+)\s+(\d+)\s*$")


@dataclass(frozen=True)
class KernelStat:
    """One kernel's aggregate time on the device."""

    name: str
    time_ns: int
    instances: int


@dataclass
class NsightStats:
    """Normalized device-time breakdown."""

    kernel_ns: int = 0
    memcpy_htod_ns: int = 0
    memcpy_dtoh_ns: int = 0
    sync_ns: int = 0
    cpu_ns: int = 0
    kernels: list[KernelStat] = field(default_factory=list)

    @property
    def memcpy_ns(self) -> int:
        return self.memcpy_htod_ns + self.memcpy_dtoh_ns

    @property
    def total_ns(self) -> int:
        return self.kernel_ns + self.memcpy_ns + self.sync_ns + self.cpu_ns


@dataclass(frozen=True)
class BottleneckReport:
    """The classified bottleneck plus deterministic guidance."""

    kind: str
    rationale: str
    recommendations: tuple[str, ...]
    breakdown: dict[str, float]

    def to_dict(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "rationale": self.rationale,
            "recommendations": list(self.recommendations),
            "breakdown_pct": self.breakdown,
        }

    def render(self) -> str:
        lines = [
            "# nsight bottleneck analysis",
            f"bottleneck: {self.kind}",
            f"why: {self.rationale}",
            "",
            "time breakdown:",
        ]
        for name, pct in sorted(self.breakdown.items(), key=lambda kv: kv[1], reverse=True):
            lines.append(f"  {name:<8} {pct:5.1f}%")
        lines.append("")
        lines.append("recommendations:")
        lines += [f"  - {r}" for r in self.recommendations]
        return "\n".join(lines) + "\n"


_RECOMMENDATIONS: dict[str, tuple[str, ...]] = {
    "compute_bound": (
        "kernels dominate; profile the top kernel with Nsight Compute for occupancy",
        "consider lower precision (FP16/INT8) or a lighter model variant",
        "fuse elementwise ops and check for register/shared-memory spills",
    ),
    "memory_bound": (
        "host<->device copies dominate; keep tensors resident on the GPU across frames",
        "use pinned host memory and overlap copies with compute via CUDA streams",
        "batch transfers and avoid per-frame reallocation",
    ),
    "sync_bound": (
        "synchronization stalls dominate; remove unnecessary cudaDeviceSynchronize calls",
        "use events and async APIs so CPU and GPU overlap",
        "pipeline stages across streams instead of serializing them",
    ),
    "cpu_bound": (
        "CPU work dominates; the GPU is starved, move pre/post-processing off the hot path",
        "parallelize CPU stages or offload them (NVDEC/VPI/DLA)",
        "check for Python/GIL or single-threaded bottlenecks feeding the pipeline",
    ),
    "balanced": ("no single stage dominates; optimize the largest slice first",),
}


def classify_bottleneck(stats: NsightStats, dominance: float = 0.5) -> BottleneckReport:
    """Classify the dominant time sink; deterministic thresholds only."""
    total = stats.total_ns
    slices = {
        "kernel": stats.kernel_ns,
        "memcpy": stats.memcpy_ns,
        "sync": stats.sync_ns,
        "cpu": stats.cpu_ns,
    }
    if total <= 0:
        return BottleneckReport(
            kind="unknown",
            rationale="no timing signal was captured",
            recommendations=("verify the nsys wrapper emitted NSIGHT summary lines",),
            breakdown={k: 0.0 for k in slices},
        )
    breakdown = {name: value / total * 100.0 for name, value in slices.items()}
    top_name, top_value = max(slices.items(), key=lambda kv: kv[1])
    kind_map = {
        "kernel": "compute_bound",
        "memcpy": "memory_bound",
        "sync": "sync_bound",
        "cpu": "cpu_bound",
    }
    if top_value / total >= dominance:
        kind = kind_map[top_name]
        rationale = f"{top_name} is {breakdown[top_name]:.0f}% of device time"
    else:
        kind = "balanced"
        rationale = f"largest slice ({top_name}) is only {breakdown[top_name]:.0f}% of device time"
    return BottleneckReport(
        kind=kind,
        rationale=rationale,
        recommendations=_RECOMMENDATIONS[kind],
        breakdown=breakdown,
    )


def parse_nsight_report(text: str) -> NsightStats:
    """Parse normalized NSIGHT summary lines into stats."""
    stats = NsightStats()
    for line in text.splitlines():
        scalar = _SCALAR.match(line)
        if scalar:
            setattr(stats, scalar.group(1), int(scalar.group(2)))
            continue
        kernel = _KERNEL.match(line)
        if kernel:
            stats.kernels.append(
                KernelStat(
                    name=kernel.group(1),
                    time_ns=int(kernel.group(2)),
                    instances=int(kernel.group(3)),
                )
            )
    return stats


@dataclass
class NsightResult:
    """Parsed stats plus the classified bottleneck."""

    stats: NsightStats
    report: BottleneckReport

    def to_dict(self) -> dict[str, object]:
        return {
            "kernel_ns": self.stats.kernel_ns,
            "memcpy_ns": self.stats.memcpy_ns,
            "sync_ns": self.stats.sync_ns,
            "cpu_ns": self.stats.cpu_ns,
            "top_kernels": [
                {"name": k.name, "time_ns": k.time_ns, "instances": k.instances}
                for k in sorted(self.stats.kernels, key=lambda k: k.time_ns, reverse=True)[:5]
            ],
            "analysis": self.report.to_dict(),
        }

    def render(self) -> str:
        lines = [self.report.render()]
        if self.stats.kernels:
            lines.append("top kernels:")
            for k in sorted(self.stats.kernels, key=lambda k: k.time_ns, reverse=True)[:5]:
                lines.append(f"  {k.name:<28} {k.time_ns / 1e6:8.2f} ms  x{k.instances}")
        return "\n".join(lines) + "\n"

    def persist(self, run_dir: Path) -> None:
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "nsight.json").write_text(json.dumps(self.to_dict(), indent=2))
        (run_dir / "nsight.txt").write_text(self.render())


class NsightProfiler:
    """Runs the nsys wrapper on a target and analyzes the trace."""

    def __init__(self, board_id: str, run_dir: Path) -> None:
        self._board_id = board_id
        self._run_dir = run_dir

    async def run(self, command: str, capture_s: float = 120.0) -> NsightResult:
        board = get_board(self._board_id)
        _logger.info("nsight_profile", board=self._board_id)
        async with open_runner(board) as runner:
            result = await runner.run(command, timeout_s=capture_s)
        output = result.stdout + result.stderr
        self._run_dir.mkdir(parents=True, exist_ok=True)
        (self._run_dir / "nsys-output.txt").write_text(output)
        stats = parse_nsight_report(output)
        analysis = NsightResult(stats=stats, report=classify_bottleneck(stats))
        analysis.persist(self._run_dir)
        return analysis
