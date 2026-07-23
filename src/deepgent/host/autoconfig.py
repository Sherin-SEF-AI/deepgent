"""Auto-configuration from a detected host profile.

Maps a HostProfile to a recommended runtime configuration: which toolchain
applies, whether the local machine can execute tasks directly, and the
default target. Writing is idempotent and never clobbers operator settings
already present in the config file.
"""

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import structlog
import tomli_w

from deepgent.host.detect import HostProfile

_logger = structlog.get_logger(__name__)

USER_CONFIG_RELPATH = Path(".deepgent") / "config.toml"

# device class -> the toolchain that produces artifacts for it. "native"
# means build and run on this host directly; a container name means a
# version-pinned cross-toolchain applies.
_TOOLCHAIN_BY_CLASS = {
    "jetson": "jp6",
    "raspberry-pi": "native",
    "linux-desktop": "native",
    "linux-server": "native",
    "macos": "native",
    "windows": "native",
    "unknown": "native",
}


@dataclass(frozen=True)
class HostConfig:
    """Recommended configuration derived from a host profile."""

    device_class: str
    toolchain: str
    local_execution: bool
    accelerator: str
    capabilities: tuple[str, ...]

    def to_table(self) -> dict[str, Any]:
        return {
            "device_class": self.device_class,
            "toolchain": self.toolchain,
            "local_execution": self.local_execution,
            "accelerator": self.accelerator,
            "capabilities": list(self.capabilities),
        }


def _capabilities(profile: HostProfile) -> tuple[str, ...]:
    caps: list[str] = []
    if profile.accelerator in ("tegra", "cuda-discrete"):
        caps.append("cuda")
    if profile.accelerator == "hailo":
        caps.append("hailo")
    if profile.accelerator == "rocm":
        caps.append("rocm")
    if profile.accelerator == "apple-silicon":
        caps.append("metal")
    if profile.container_runtime:
        caps.append("containers")
    return tuple(caps)


def derive_config(profile: HostProfile) -> HostConfig:
    """Recommended configuration for a detected host."""
    toolchain = _TOOLCHAIN_BY_CLASS.get(profile.device_class, "native")
    # A host runs tasks locally when it is not a remote-only cross target.
    # Jetson boards are targeted over SSH in the farm, but a Jetson can also
    # run deepgent itself; local_execution reflects "this machine can build
    # and run its own artifacts".
    local_execution = profile.os in ("Linux", "Darwin")
    return HostConfig(
        device_class=profile.device_class,
        toolchain=toolchain,
        local_execution=local_execution,
        accelerator=profile.accelerator,
        capabilities=_capabilities(profile),
    )


def _load_config(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    with path.open("rb") as f:
        return tomllib.load(f)


def apply_config(
    profile: HostProfile, config_path: Path | None = None, force: bool = False
) -> Path:
    """Write the detected host config into ~/.deepgent/config.toml.

    The [host] block is refreshed from detection every run (it describes the
    machine, not operator intent). Operator keys elsewhere (budget, boards,
    knowledge) are preserved. A pre-existing [host] block is only overwritten
    with force, so a manual override survives re-runs.
    """
    path = config_path if config_path is not None else Path.home() / USER_CONFIG_RELPATH
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = _load_config(path)
    host_config = derive_config(profile)

    if "host" in existing and not force:
        _logger.info("host_config_kept", path=str(path))
        return path

    existing["host"] = {
        **host_config.to_table(),
        "device_model": profile.device_model or "",
        "arch": profile.arch,
        "detected_os": f"{profile.os} {profile.os_version or ''}".strip(),
    }
    # A sensible default board name for local execution, without clobbering an
    # operator-set default_board.
    if host_config.local_execution and "default_board" not in existing:
        existing["default_board"] = "local"
    with path.open("wb") as f:
        tomli_w.dump(existing, f)
    _logger.info("host_config_written", path=str(path), toolchain=host_config.toolchain)
    return path
