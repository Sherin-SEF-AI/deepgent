"""Host layer: detect the local machine and auto-configure deepgent for it."""

from deepgent.host.autoconfig import HostConfig, apply_config, derive_config
from deepgent.host.detect import HostProfile, detect_host

__all__ = [
    "HostConfig",
    "HostProfile",
    "apply_config",
    "derive_config",
    "detect_host",
]
