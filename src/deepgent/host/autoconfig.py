"""Auto-configuration from a detected host profile.

Maps a HostProfile to a recommended runtime configuration: which toolchain
applies, whether the local machine can execute tasks directly, and the
default target. Config writes are atomic (temp file + os.replace) so a
concurrent setup or a crash never leaves a half-written config. Operator
settings already present are preserved; an operator-pinned [host] value is
never overwritten by detection.
"""

import os
import tempfile
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import structlog
import tomli_w

from deepgent.errors import ConfigError
from deepgent.host.detect import (
    DETECTOR_VERSION,
    HostProfile,
    is_valid_device_class,
)

_logger = structlog.get_logger(__name__)

USER_CONFIG_RELPATH = Path(".deepgent") / "config.toml"

# device class -> toolchain. "native" means build and run on this host
# directly; a container name means a version-pinned cross-toolchain applies.
_TOOLCHAIN_BY_CLASS = {
    "jetson": "jp6",
    "raspberry-pi": "native",
    "linux-desktop": "native",
    "linux-server": "native",
    "wsl": "native",
    "container": "native",
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
    if profile.accelerator in ("tegra", "cuda-discrete", "multi-gpu"):
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
    # local_execution reflects "this machine can build and run its own
    # artifacts". Every Unix-like host qualifies; Windows is targeted, not a
    # local executor, until first-class Windows support lands.
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
    try:
        with path.open("rb") as f:
            return tomllib.load(f)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(
            f"existing config {path} is not valid TOML: {exc}; fix it or pass "
            "--force to replace the [host] block"
        ) from exc
    except OSError as exc:
        raise ConfigError(f"cannot read config {path}: {exc}") from exc


def _atomic_write(path: Path, data: dict[str, Any]) -> None:
    """Write config atomically so a concurrent setup or crash never leaves a
    partial file. Temp file is created in the same directory for a same-fs
    rename."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=".config-", suffix=".toml")
    except OSError as exc:
        raise ConfigError(f"cannot write host config to {path}: {exc}") from exc
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as f:
            tomli_w.dump(data, f)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except OSError as exc:
        tmp.unlink(missing_ok=True)
        raise ConfigError(f"cannot write host config to {path}: {exc}") from exc


def apply_config(
    profile: HostProfile, config_path: Path | None = None, force: bool = False
) -> tuple[Path, bool]:
    """Write the detected host config into ~/.deepgent/config.toml.

    Returns (path, written). The [host] block is only written when absent or
    force=True; an operator-pinned block (host.pinned = true) is never
    overwritten. Operator keys elsewhere (budget, boards, knowledge) are
    preserved. Raises ConfigError with an actionable message on corrupt or
    unwritable config.
    """
    path = config_path if config_path is not None else Path.home() / USER_CONFIG_RELPATH
    existing = _load_config(path)
    host_config = derive_config(profile)

    existing_host = existing.get("host")
    if isinstance(existing_host, dict):
        if existing_host.get("pinned"):
            _logger.info("host_config_pinned_kept", path=str(path))
            return path, False
        if not force:
            _logger.info("host_config_kept", path=str(path))
            return path, False

    existing["host"] = {
        **host_config.to_table(),
        "device_model": profile.device_model or "",
        "arch": profile.arch,
        "detected_os": f"{profile.os} {profile.os_version or ''}".strip(),
        "detected_at": profile.detected_at,
        "detector_version": DETECTOR_VERSION,
        "pinned": False,
    }
    if host_config.local_execution and "default_board" not in existing:
        existing["default_board"] = "local"

    _atomic_write(path, existing)
    _logger.info("host_config_written", path=str(path), toolchain=host_config.toolchain)
    return path, True


def pin_host_override(
    config_path: Path,
    device_class: str | None = None,
    toolchain: str | None = None,
) -> None:
    """Pin operator-chosen host values so detection never overwrites them.

    Used when detection is wrong (e.g. an exotic board) and the operator
    forces the class/toolchain. Validates the class against the known set.
    """
    if device_class is not None and not is_valid_device_class(device_class):
        raise ConfigError(
            f"'{device_class}' is not a valid device class; valid: "
            + ", ".join(sorted(_TOOLCHAIN_BY_CLASS))
        )
    existing = _load_config(config_path)
    host = existing.get("host")
    if not isinstance(host, dict):
        host = {}
    host["pinned"] = True
    if device_class is not None:
        host["device_class"] = device_class
        host["toolchain"] = _TOOLCHAIN_BY_CLASS[device_class]
    if toolchain is not None:
        host["toolchain"] = toolchain
    existing["host"] = host
    _atomic_write(config_path, existing)
    _logger.info("host_config_pinned", path=str(config_path), device_class=device_class)
