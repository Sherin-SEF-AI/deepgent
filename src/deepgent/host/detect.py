"""Host detection: profile the machine deepgent runs on.

Every fact is read from a real file or command, never assumed (prime
directive). What cannot be determined is left None, not fabricated. The
resulting HostProfile drives auto-configuration: which toolchain applies,
whether local execution is viable, and what accelerator is present.
"""

import platform
import re
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

import structlog

_logger = structlog.get_logger(__name__)

DeviceClass = Literal[
    "jetson",
    "raspberry-pi",
    "linux-desktop",
    "linux-server",
    "macos",
    "windows",
    "unknown",
]
Accelerator = Literal["tegra", "cuda-discrete", "rocm", "hailo", "apple-silicon", "none"]


@dataclass(frozen=True)
class GpuInfo:
    """A detected GPU/accelerator."""

    name: str
    memory_mb: int | None
    source: str  # where the fact came from


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
    device_model: str | None = None  # e.g. "NVIDIA Jetson AGX Orin", "Raspberry Pi 5"
    l4t: str | None = None
    container_runtime: str | None = None
    disk_free_gb: float | None = None

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
            f"ram:           {self.ram_mb} MB" if self.ram_mb else "ram:           unknown",
            f"accelerator:   {self.accelerator}",
        ]
        for gpu in self.gpus:
            mem = f", {gpu.memory_mb} MB" if gpu.memory_mb else ""
            lines.append(f"  gpu:         {gpu.name}{mem} [{gpu.source}]")
        if self.l4t:
            lines.append(f"l4t:           {self.l4t}")
        lines.append(f"container:     {self.container_runtime or 'none detected'}")
        if self.disk_free_gb is not None:
            lines.append(f"disk free:     {self.disk_free_gb:.0f} GB")
        lines.append(f"python:        {self.python_version}")
        return "\n".join(lines) + "\n"


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


def _run(cmd: list[str]) -> str | None:
    if shutil.which(cmd[0]) is None:
        return None
    try:
        completed = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    except (subprocess.SubprocessError, OSError):
        return None
    return completed.stdout if completed.returncode == 0 else None


def _l4t_version() -> str | None:
    raw = _read_text("/etc/nv_tegra_release")
    if not raw:
        return None
    # e.g. "# R36 (release), REVISION: 4.3, ..."
    rel = re.search(r"R(\d+).*REVISION:\s*([\d.]+)", raw)
    return f"{rel.group(1)}.{rel.group(2)}" if rel else raw.splitlines()[0].strip()


def _detect_gpus() -> tuple[list[GpuInfo], Accelerator]:
    gpus: list[GpuInfo] = []
    accelerator: Accelerator = "none"

    # Jetson integrated GPU: tegra release file is the ground truth.
    if Path("/etc/nv_tegra_release").is_file():
        model = _device_tree_model() or "NVIDIA Tegra"
        gpus.append(GpuInfo(name=model, memory_mb=None, source="tegra"))
        return gpus, "tegra"

    smi = _run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"])
    if smi:
        for line in smi.strip().splitlines():
            parts = [p.strip() for p in line.split(",")]
            if parts and parts[0]:
                mem = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else None
                gpus.append(GpuInfo(name=parts[0], memory_mb=mem, source="nvidia-smi"))
        if gpus:
            accelerator = "cuda-discrete"

    if Path("/dev/hailo0").exists():
        gpus.append(GpuInfo(name="Hailo accelerator", memory_mb=None, source="/dev/hailo0"))
        if accelerator == "none":
            accelerator = "hailo"

    if platform.system() == "Darwin" and platform.machine() == "arm64":
        gpus.append(GpuInfo(name="Apple Silicon GPU", memory_mb=None, source="platform"))
        if accelerator == "none":
            accelerator = "apple-silicon"

    if accelerator == "none" and _run(["rocminfo"]):
        accelerator = "rocm"
    return gpus, accelerator


def _device_class(model: str | None, accelerator: Accelerator, ram_mb: int | None) -> DeviceClass:
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
    # Heuristic: a discrete GPU or lots of RAM reads as a desktop/workstation;
    # otherwise a headless server. Both run tasks locally the same way.
    if accelerator == "cuda-discrete" or (ram_mb is not None and ram_mb >= 16000):
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


def detect_host() -> HostProfile:
    """Profile the local machine from real system sources."""
    model = _device_tree_model()
    ram = _ram_mb()
    gpus, accelerator = _detect_gpus()
    device_class = _device_class(model, accelerator, ram)
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
    )
    _logger.info(
        "host_detected",
        device_class=device_class,
        accelerator=accelerator,
        arch=profile.arch,
    )
    return profile


def _cpu_count() -> int:
    import os

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
