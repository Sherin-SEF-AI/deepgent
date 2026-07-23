"""Host detection: profile the machine deepgent runs on.

Every fact is read from a real file or command, never assumed (prime
directive). What cannot be determined is left None, not fabricated. Detection
performs no network I/O (offline-safe by construction) and bounds every
external probe and its own total wall-clock so a hung driver can never hang
setup. The resulting HostProfile drives auto-configuration.
"""

import os
import platform
import re
import shutil
import subprocess
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal

import structlog

_logger = structlog.get_logger(__name__)

# Bumped when the detection logic changes in a way that could alter a stored
# profile; lets telemetry and drift checks correlate.
DETECTOR_VERSION = 2

# Per-external-command hard timeout and total detection wall-clock budget.
_PROBE_TIMEOUT_S = 15.0
_DETECTION_BUDGET_S = 30.0

DeviceClass = Literal[
    "jetson",
    "raspberry-pi",
    "linux-desktop",
    "linux-server",
    "wsl",
    "container",
    "macos",
    "windows",
    "unknown",
]
Accelerator = Literal[
    "tegra", "cuda-discrete", "multi-gpu", "rocm", "hailo", "apple-silicon", "none"
]

_VALID_DEVICE_CLASSES: frozenset[str] = frozenset(DeviceClass.__args__)  # type: ignore[attr-defined]
_VALID_ACCELERATORS: frozenset[str] = frozenset(Accelerator.__args__)  # type: ignore[attr-defined]


@dataclass(frozen=True)
class GpuInfo:
    """A detected GPU/accelerator."""

    name: str
    memory_mb: int | None
    source: str  # where the fact came from


@dataclass(frozen=True)
class ResourceLimits:
    """Effective (cgroup-enforced) CPU/RAM limits, distinct from physical."""

    cpu_effective: float | None  # cgroup CPU quota in cores, if capped
    ram_limit_mb: int | None  # cgroup memory limit, if capped


@dataclass(frozen=True)
class HostProfile:
    """Empirically detected specification of the local machine."""

    os: str
    os_version: str | None
    arch: str
    cpu_model: str | None
    cpu_count: int
    ram_mb: int | None
    python_version: str
    device_class: DeviceClass
    accelerator: Accelerator
    gpus: tuple[GpuInfo, ...] = ()
    device_model: str | None = None
    l4t: str | None = None
    container_runtime: str | None = None
    disk_free_gb: float | None = None
    limits: ResourceLimits = field(
        default_factory=lambda: ResourceLimits(cpu_effective=None, ram_limit_mb=None)
    )
    notes: tuple[str, ...] = ()
    detected_at: float = 0.0
    detector_version: int = DETECTOR_VERSION

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["gpus"] = [asdict(g) for g in self.gpus]
        return data

    def render(self) -> str:
        lines = [
            "# host profile",
            "",
            f"device class:  {self.device_class}",
            f"model:         {self.device_model or '-'}",
            f"os:            {self.os} {self.os_version or ''}".rstrip(),
            f"arch:          {self.arch}",
            f"cpu:           {self.cpu_model or '?'} ({self.cpu_count} threads)",
        ]
        if self.limits.cpu_effective is not None:
            lines.append(f"cpu limit:     {self.limits.cpu_effective:.2f} cores (cgroup)")
        lines.append(
            f"ram:           {self.ram_mb} MB" if self.ram_mb else "ram:           unknown"
        )
        if self.limits.ram_limit_mb is not None:
            lines.append(f"ram limit:     {self.limits.ram_limit_mb} MB (cgroup)")
        lines.append(f"accelerator:   {self.accelerator}")
        for gpu in self.gpus:
            mem = f", {gpu.memory_mb} MB" if gpu.memory_mb else ""
            lines.append(f"  gpu:         {gpu.name}{mem} [{gpu.source}]")
        if self.l4t:
            lines.append(f"l4t:           {self.l4t}")
        lines.append(f"container:     {self.container_runtime or 'none detected'}")
        if self.disk_free_gb is not None:
            lines.append(f"disk free:     {self.disk_free_gb:.0f} GB")
        lines.append(f"python:        {self.python_version}")
        for note in self.notes:
            lines.append(f"note:          {note}")
        return "\n".join(lines) + "\n"


def is_valid_device_class(value: str) -> bool:
    return value in _VALID_DEVICE_CLASSES


def is_valid_accelerator(value: str) -> bool:
    return value in _VALID_ACCELERATORS


def _read_text(path: str) -> str | None:
    try:
        return Path(path).read_text(errors="replace")
    except OSError:
        return None


def _device_tree_model() -> str | None:
    raw = _read_text("/proc/device-tree/model")
    return raw.replace("\x00", "").strip() if raw else None


def _cpu_model() -> str | None:
    cpuinfo = _read_text("/proc/cpuinfo")
    if cpuinfo:
        for line in cpuinfo.splitlines():
            if line.startswith(("model name", "Model")):
                return line.split(":", 1)[1].strip()
    if platform.system() == "Darwin":
        out = _run(["sysctl", "-n", "machdep.cpu.brand_string"])
        if out:
            return out.strip()
    return platform.processor() or None


def _ram_mb() -> int | None:
    meminfo = _read_text("/proc/meminfo")
    if meminfo:
        match = re.search(r"MemTotal:\s+(\d+) kB", meminfo)
        if match:
            return int(match.group(1)) // 1024
    if platform.system() == "Darwin":
        out = _run(["sysctl", "-n", "hw.memsize"])
        if out and out.strip().isdigit():
            return int(out.strip()) // (1024 * 1024)
    return None


@dataclass
class _ProbeBudget:
    """Tracks total external-probe wall-clock against the detection budget."""

    deadline: float
    truncated: bool = False

    def remaining(self) -> float:
        return self.deadline - time.monotonic()

    def exhausted(self) -> bool:
        return self.remaining() <= 0


def _run(cmd: list[str], budget: _ProbeBudget | None = None) -> str | None:
    """Run an allowlisted binary with no shell, bounded by the probe timeout
    and any remaining detection budget. Never raises; returns None on any
    failure, absence, or timeout."""
    if shutil.which(cmd[0]) is None:
        return None
    timeout = _PROBE_TIMEOUT_S
    if budget is not None:
        remaining = budget.remaining()
        if remaining <= 0:
            budget.truncated = True
            return None
        timeout = min(timeout, remaining)
    try:
        completed = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        _logger.warning("probe_timeout", command=cmd[0], timeout_s=round(timeout, 1))
        if budget is not None:
            budget.truncated = True
        return None
    except OSError:
        return None
    return completed.stdout if completed.returncode == 0 else None


def _l4t_version() -> str | None:
    raw = _read_text("/etc/nv_tegra_release")
    if not raw:
        return None
    rel = re.search(r"R(\d+).*REVISION:\s*([\d.]+)", raw)
    return f"{rel.group(1)}.{rel.group(2)}" if rel else raw.splitlines()[0].strip()


def _nvidia_gpus(budget: _ProbeBudget, notes: list[str]) -> list[GpuInfo]:
    """Discrete NVIDIA GPUs via nvidia-smi, with one retry on transient
    failure and an explicit note when the tool is present but errors."""
    if shutil.which("nvidia-smi") is None:
        return []
    query = ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"]
    out = _run(query, budget)
    if out is None:
        out = _run(query, budget)  # single retry for a transient driver hiccup
    if out is None:
        notes.append("nvidia-smi is present but returned no usable output (driver issue?)")
        return []
    gpus: list[GpuInfo] = []
    for line in out.strip().splitlines():
        parts = [p.strip() for p in line.split(",")]
        if not parts or not parts[0] or "no devices" in parts[0].lower():
            continue
        mem = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else None
        gpus.append(GpuInfo(name=parts[0], memory_mb=mem, source="nvidia-smi"))
    if not gpus:
        notes.append("nvidia-smi found no CUDA devices")
    return gpus


def _detect_gpus(budget: _ProbeBudget, notes: list[str]) -> tuple[list[GpuInfo], Accelerator]:
    # Jetson integrated GPU: the tegra release file is ground truth.
    if Path("/etc/nv_tegra_release").is_file():
        model = _device_tree_model() or "NVIDIA Tegra"
        return [GpuInfo(name=model, memory_mb=None, source="tegra")], "tegra"

    gpus = _nvidia_gpus(budget, notes)
    accelerator: Accelerator = "none"
    if len(gpus) > 1:
        accelerator = "multi-gpu"
    elif gpus:
        accelerator = "cuda-discrete"

    if Path("/dev/hailo0").exists():
        gpus.append(GpuInfo(name="Hailo accelerator", memory_mb=None, source="/dev/hailo0"))
        if accelerator == "none":
            accelerator = "hailo"

    if platform.system() == "Darwin" and platform.machine() == "arm64":
        gpus.append(GpuInfo(name="Apple Silicon GPU", memory_mb=None, source="platform"))
        if accelerator == "none":
            accelerator = "apple-silicon"

    if accelerator == "none" and _run(["rocminfo"], budget):
        accelerator = "rocm"
    return gpus, accelerator


def _is_wsl() -> bool:
    for src in ("/proc/sys/kernel/osrelease", "/proc/version"):
        text = _read_text(src)
        if text and ("microsoft" in text.lower() or "wsl" in text.lower()):
            return True
    return False


def _is_container() -> bool:
    if Path("/.dockerenv").exists() or Path("/run/.containerenv").exists():
        return True
    cgroup = _read_text("/proc/1/cgroup")
    if cgroup and re.search(r"docker|kubepods|containerd|libpod|lxc", cgroup):
        return True
    # systemd exposes the container type directly.
    env = _read_text("/run/systemd/container")
    return bool(env and env.strip())


def _cgroup_limits() -> ResourceLimits:
    """Effective CPU/RAM caps enforced by cgroups (v2 first, then v1)."""
    cpu_effective: float | None = None
    ram_limit_mb: int | None = None

    v2_cpu = _read_text("/sys/fs/cgroup/cpu.max")
    if v2_cpu:
        parts = v2_cpu.split()
        if len(parts) == 2 and parts[0] != "max" and parts[1].isdigit():
            quota, period = int(parts[0]), int(parts[1])
            if period > 0:
                cpu_effective = quota / period
    else:
        quota_s = _read_text("/sys/fs/cgroup/cpu/cpu.cfs_quota_us")
        period_s = _read_text("/sys/fs/cgroup/cpu/cpu.cfs_period_us")
        if quota_s and period_s:
            quota, period = int(quota_s.strip()), int(period_s.strip())
            if quota > 0 and period > 0:
                cpu_effective = quota / period

    for path in ("/sys/fs/cgroup/memory.max", "/sys/fs/cgroup/memory/memory.limit_in_bytes"):
        raw = _read_text(path)
        if raw and raw.strip().isdigit():
            value = int(raw.strip())
            # A very large limit means "unlimited"; ignore it.
            if 0 < value < (1 << 62):
                ram_limit_mb = value // (1024 * 1024)
            break
    return ResourceLimits(cpu_effective=cpu_effective, ram_limit_mb=ram_limit_mb)


def _device_class(
    model: str | None, accelerator: Accelerator, ram_mb: int | None, in_container: bool
) -> DeviceClass:
    system = platform.system()
    if system == "Darwin":
        return "macos"
    if system == "Windows":
        return "windows"
    if system != "Linux":
        return "unknown"
    if accelerator == "tegra":
        return "jetson"
    if model and "raspberry pi" in model.lower():
        return "raspberry-pi"
    if _is_wsl():
        return "wsl"
    if in_container:
        return "container"
    if accelerator in ("cuda-discrete", "multi-gpu") or (ram_mb is not None and ram_mb >= 16000):
        return "linux-desktop"
    return "linux-server"


def _container_runtime() -> str | None:
    for runtime in ("docker", "podman", "nerdctl"):
        if shutil.which(runtime):
            return runtime
    return None


def _disk_free_gb() -> float | None:
    try:
        usage = shutil.disk_usage(Path.home())
    except OSError:
        return None
    return usage.free / (1024**3)


def _cpu_count() -> int:
    return os.cpu_count() or 1


def _os_version() -> str | None:
    release = _read_text("/etc/os-release")
    if release:
        match = re.search(r'^VERSION_ID="?([^"\n]+)"?', release, re.MULTILINE)
        if match:
            return match.group(1)
    if platform.system() == "Darwin":
        return platform.mac_ver()[0] or None
    return platform.release() or None


def _macos_model() -> str | None:
    if platform.system() != "Darwin":
        return None
    out = _run(["sysctl", "-n", "hw.model"])
    return out.strip() if out else None


def detect_host(now: float | None = None) -> HostProfile:
    """Profile the local machine from real system sources.

    now is injectable so callers (and tests) get a deterministic detected_at
    without this function reaching for a live clock implicitly.
    """
    budget = _ProbeBudget(deadline=time.monotonic() + _DETECTION_BUDGET_S)
    notes: list[str] = []

    model = _device_tree_model()
    ram = _ram_mb()
    gpus, accelerator = _detect_gpus(budget, notes)
    in_container = _is_container()
    device_class = _device_class(model, accelerator, ram, in_container)
    limits = _cgroup_limits()
    if budget.truncated:
        notes.append("detection truncated: external probe budget exceeded")

    profile = HostProfile(
        os=platform.system(),
        os_version=_os_version(),
        arch=platform.machine(),
        cpu_model=_cpu_model(),
        cpu_count=_cpu_count(),
        ram_mb=ram,
        python_version=platform.python_version(),
        device_class=device_class,
        accelerator=accelerator,
        gpus=tuple(gpus),
        device_model=model or _macos_model(),
        l4t=_l4t_version(),
        container_runtime=_container_runtime(),
        disk_free_gb=_disk_free_gb(),
        limits=limits,
        notes=tuple(notes),
        detected_at=now if now is not None else time.time(),
    )
    _logger.info(
        "host_detected",
        device_class=device_class,
        accelerator=accelerator,
        arch=profile.arch,
        notes=len(notes),
    )
    return profile
