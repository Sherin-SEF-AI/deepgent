"""Host layer: detect the local machine and auto-configure deepgent for it."""

from deepgent.host.autoconfig import (
    HostConfig,
    apply_config,
    derive_config,
    pin_host_override,
)
from deepgent.host.detect import (
    DETECTOR_VERSION,
    GpuInfo,
    HostProfile,
    ResourceLimits,
    detect_host,
    is_valid_accelerator,
    is_valid_device_class,
)

__all__ = [
    "DETECTOR_VERSION",
    "GpuInfo",
    "HostConfig",
    "HostProfile",
    "ResourceLimits",
    "apply_config",
    "derive_config",
    "detect_host",
    "is_valid_accelerator",
    "is_valid_device_class",
    "pin_host_override",
]
