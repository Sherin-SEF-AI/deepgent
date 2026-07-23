"""Generic host metrics: a universal counterpart to tegrastats.

On non-Jetson hosts, samples CPU load (/proc/stat), memory (/proc/meminfo),
thermal zones (/sys/class/thermal), and NVIDIA discrete-GPU utilization and
power (nvidia-smi when present). Produces the same summary-metric shape as
the tegrastats parser so goldens, soak, and differential runs score
identically regardless of target class.
"""

import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from statistics import mean

_STAT = Path("/proc/stat")
_MEMINFO = Path("/proc/meminfo")
_THERMAL_GLOB = "/sys/class/thermal/thermal_zone*/temp"


@dataclass(frozen=True)
class GenericSample:
    """One generic host sample."""

    cpu_pct: float | None
    ram_used_mb: int | None
    ram_total_mb: int | None
    temp_max_c: float | None
    gpu_pct: float | None
    power_w: float | None


def _cpu_times() -> tuple[int, int] | None:
    """(idle, total) jiffies from /proc/stat's aggregate cpu line."""
    try:
        first = _STAT.read_text().splitlines()[0]
    except (OSError, IndexError):
        return None
    if not first.startswith("cpu "):
        return None
    fields = [int(x) for x in first.split()[1:]]
    idle = fields[3] + (fields[4] if len(fields) > 4 else 0)
    return idle, sum(fields)


def _ram() -> tuple[int, int] | None:
    try:
        text = _MEMINFO.read_text()
    except OSError:
        return None
    total = re.search(r"MemTotal:\s+(\d+) kB", text)
    avail = re.search(r"MemAvailable:\s+(\d+) kB", text)
    if not total or not avail:
        return None
    total_mb = int(total.group(1)) // 1024
    used_mb = total_mb - int(avail.group(1)) // 1024
    return used_mb, total_mb


def _temp_max_c() -> float | None:
    import glob

    temps = []
    for path in glob.glob(_THERMAL_GLOB):
        try:
            millideg = int(Path(path).read_text().strip())
            temps.append(millideg / 1000.0)
        except (OSError, ValueError):
            continue
    return max(temps) if temps else None


def _nvidia_gpu() -> tuple[float | None, float | None]:
    """(utilization %, power W) from nvidia-smi, or (None, None)."""
    import shutil

    if shutil.which("nvidia-smi") is None:
        return None, None
    try:
        out = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=utilization.gpu,power.draw",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (subprocess.SubprocessError, OSError):
        return None, None
    if out.returncode != 0 or not out.stdout.strip():
        return None, None
    line = out.stdout.strip().splitlines()[0]
    parts = [p.strip() for p in line.split(",")]
    util = float(parts[0]) if parts and _is_num(parts[0]) else None
    power = float(parts[1]) if len(parts) > 1 and _is_num(parts[1]) else None
    return util, power


def _is_num(value: str) -> bool:
    try:
        float(value)
        return True
    except ValueError:
        return False


def sample_once(cpu_window_s: float = 0.2) -> GenericSample:
    """Take one generic host sample."""
    before = _cpu_times()
    time.sleep(cpu_window_s)
    after = _cpu_times()
    cpu_pct: float | None = None
    if before and after:
        idle_delta = after[0] - before[0]
        total_delta = after[1] - before[1]
        if total_delta > 0:
            cpu_pct = 100.0 * (1.0 - idle_delta / total_delta)

    ram = _ram()
    gpu_pct, power = _nvidia_gpu()
    return GenericSample(
        cpu_pct=cpu_pct,
        ram_used_mb=ram[0] if ram else None,
        ram_total_mb=ram[1] if ram else None,
        temp_max_c=_temp_max_c(),
        gpu_pct=gpu_pct,
        power_w=power,
    )


def summarize_generic(
    samples: list[GenericSample], interval_ms: int | None = None
) -> dict[str, float]:
    """Summary metrics matching the tegrastats shape where they overlap."""
    metrics: dict[str, float] = {"samples": float(len(samples))}
    if not samples:
        return metrics
    cpus = [s.cpu_pct for s in samples if s.cpu_pct is not None]
    if cpus:
        metrics["cpu_max_pct"] = max(cpus)
        metrics["cpu_mean_pct"] = mean(cpus)
    rams = [s.ram_used_mb for s in samples if s.ram_used_mb is not None]
    if rams:
        metrics["ram_used_max_mb"] = float(max(rams))
    temps = [s.temp_max_c for s in samples if s.temp_max_c is not None]
    if temps:
        metrics["tj_max_c"] = max(temps)
    gpus = [s.gpu_pct for s in samples if s.gpu_pct is not None]
    if gpus:
        metrics["gr3d_max_pct"] = max(gpus)
        metrics["gr3d_mean_pct"] = mean(gpus)
    powers = [s.power_w for s in samples if s.power_w is not None]
    if powers:
        metrics["power_mean_w"] = mean(powers)
        metrics["power_max_w"] = max(powers)
        if interval_ms is not None:
            metrics["energy_j"] = sum(powers) * (interval_ms / 1000.0)
    return metrics
