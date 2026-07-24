"""Board-type catalog: categorical profiles for the targets deepgent supports.

This is a navigation and onboarding aid, not a spec sheet. Each profile records
only *categorical* identity (family, toolchain family, accelerator class, and
the interface families typically present) plus what to verify. It deliberately
holds no hardware-specific facts (memory, clocks, core counts, pinouts, exact
L4T/JetPack support, DLA/NVENC availability) - per the prime directive those
must be retrieved from the datasheet with provenance or read from the board.
The `verify` note on every entry says so.
"""

from dataclasses import dataclass

FAMILIES = ("jetson", "raspberry-pi", "accelerator", "host")


@dataclass(frozen=True)
class BoardProfile:
    """A categorical profile for one board type."""

    id: str
    name: str
    family: str
    toolchain: str  # categorical toolchain family (e.g. l4t/jetpack)
    accelerator: str  # cuda-igpu | hailo-npu | cpu-only
    interfaces: tuple[str, ...]  # interface families typically present
    verify: str  # what must be confirmed from the datasheet / the board


_VERIFY_JETSON = (
    "confirm the exact module, its supported L4T/JetPack, memory, and "
    "DLA/NVENC/NVDEC availability and pinout from the module + carrier datasheets"
)
_VERIFY_PI = (
    "confirm the exact model/revision, OS image, and carrier/HAT pinout from "
    "the Raspberry Pi datasheet; RAM and interface routing vary by model"
)
_VERIFY_ACCEL = (
    "confirm the accelerator part, host attachment (PCIe/M.2), and SDK/runtime "
    "version compatibility with the host from the vendor documentation"
)

# Categorical catalog. Membership in a product family is identity, not a
# pin/register/voltage/version fact; specifics stay in `verify`.
BOARD_CATALOG: tuple[BoardProfile, ...] = (
    # --- NVIDIA Jetson series ---
    BoardProfile(
        "jetson-agx-orin",
        "Jetson AGX Orin",
        "jetson",
        "l4t/jetpack",
        "cuda-igpu",
        ("csi", "usb", "gpio", "i2c", "can", "pcie"),
        _VERIFY_JETSON,
    ),
    BoardProfile(
        "jetson-orin-nx",
        "Jetson Orin NX",
        "jetson",
        "l4t/jetpack",
        "cuda-igpu",
        ("csi", "usb", "gpio", "i2c", "pcie"),
        _VERIFY_JETSON,
    ),
    BoardProfile(
        "jetson-orin-nano",
        "Jetson Orin Nano",
        "jetson",
        "l4t/jetpack",
        "cuda-igpu",
        ("csi", "usb", "gpio", "i2c"),
        _VERIFY_JETSON,
    ),
    BoardProfile(
        "jetson-agx-xavier",
        "Jetson AGX Xavier",
        "jetson",
        "l4t/jetpack",
        "cuda-igpu",
        ("csi", "usb", "gpio", "i2c", "can", "pcie"),
        _VERIFY_JETSON,
    ),
    BoardProfile(
        "jetson-xavier-nx",
        "Jetson Xavier NX",
        "jetson",
        "l4t/jetpack",
        "cuda-igpu",
        ("csi", "usb", "gpio", "i2c"),
        _VERIFY_JETSON,
    ),
    BoardProfile(
        "jetson-tx2",
        "Jetson TX2",
        "jetson",
        "l4t/jetpack",
        "cuda-igpu",
        ("csi", "usb", "gpio", "i2c"),
        _VERIFY_JETSON,
    ),
    BoardProfile(
        "jetson-nano",
        "Jetson Nano",
        "jetson",
        "l4t/jetpack",
        "cuda-igpu",
        ("csi", "usb", "gpio", "i2c"),
        _VERIFY_JETSON,
    ),
    # --- Raspberry Pi models ---
    BoardProfile(
        "raspberry-pi-5",
        "Raspberry Pi 5",
        "raspberry-pi",
        "raspberry-pi-os",
        "cpu-only",
        ("csi", "usb", "gpio", "i2c", "spi", "pcie"),
        _VERIFY_PI,
    ),
    BoardProfile(
        "raspberry-pi-4",
        "Raspberry Pi 4",
        "raspberry-pi",
        "raspberry-pi-os",
        "cpu-only",
        ("csi", "usb", "gpio", "i2c", "spi"),
        _VERIFY_PI,
    ),
    BoardProfile(
        "raspberry-pi-3",
        "Raspberry Pi 3",
        "raspberry-pi",
        "raspberry-pi-os",
        "cpu-only",
        ("csi", "usb", "gpio", "i2c", "spi"),
        _VERIFY_PI,
    ),
    BoardProfile(
        "raspberry-pi-zero-2w",
        "Raspberry Pi Zero 2 W",
        "raspberry-pi",
        "raspberry-pi-os",
        "cpu-only",
        ("csi", "usb", "gpio", "i2c"),
        _VERIFY_PI,
    ),
    BoardProfile(
        "raspberry-pi-cm4",
        "Raspberry Pi Compute Module 4",
        "raspberry-pi",
        "raspberry-pi-os",
        "cpu-only",
        ("csi", "usb", "gpio", "i2c", "pcie"),
        _VERIFY_PI,
    ),
    BoardProfile(
        "raspberry-pi-cm5",
        "Raspberry Pi Compute Module 5",
        "raspberry-pi",
        "raspberry-pi-os",
        "cpu-only",
        ("csi", "usb", "gpio", "i2c", "pcie"),
        _VERIFY_PI,
    ),
    # --- AI accelerators / Raspberry Pi AI HAT modules ---
    BoardProfile(
        "hailo-8-ai-hat",
        "Raspberry Pi AI HAT+ (Hailo-8)",
        "accelerator",
        "hailort",
        "hailo-npu",
        ("pcie", "m2"),
        _VERIFY_ACCEL,
    ),
    BoardProfile(
        "hailo-8l-ai-kit",
        "Raspberry Pi AI Kit (Hailo-8L)",
        "accelerator",
        "hailort",
        "hailo-npu",
        ("pcie", "m2"),
        _VERIFY_ACCEL,
    ),
    BoardProfile(
        "coral-usb",
        "Coral USB Accelerator (Edge TPU)",
        "accelerator",
        "pycoral/libedgetpu",
        "edgetpu-npu",
        ("usb",),
        _VERIFY_ACCEL,
    ),
    # --- generic hosts ---
    BoardProfile(
        "linux-desktop",
        "Generic Linux desktop/laptop",
        "host",
        "native",
        "cuda-discrete-or-cpu",
        ("usb", "pcie"),
        "read the real spec at runtime (deepgent setup); accelerator varies",
    ),
    BoardProfile(
        "macos",
        "macOS host",
        "host",
        "native",
        "cpu-or-metal",
        ("usb",),
        "read the real spec at runtime (deepgent setup); no CUDA on macOS",
    ),
)


def list_catalog(family: str | None = None) -> list[BoardProfile]:
    """All profiles, optionally filtered to one family."""
    if family is None:
        return list(BOARD_CATALOG)
    return [p for p in BOARD_CATALOG if p.family == family]


def get_profile(board_id: str) -> BoardProfile | None:
    """The profile for a catalog id, or None if unknown."""
    return next((p for p in BOARD_CATALOG if p.id == board_id), None)


def families() -> list[str]:
    """Families present in the catalog, in canonical order."""
    present = {p.family for p in BOARD_CATALOG}
    return [f for f in FAMILIES if f in present]


def suggest_capabilities(board_id: str) -> list[str]:
    """Capability tags to consider for a known board type (verify per board)."""
    profile = get_profile(board_id)
    if profile is None:
        return []
    caps = list(profile.interfaces)
    if profile.accelerator == "cuda-igpu":
        caps += ["cuda"]
    elif profile.accelerator == "hailo-npu":
        caps += ["hailo"]
    elif profile.accelerator == "edgetpu-npu":
        caps += ["edgetpu"]
    return caps


def render_catalog(profiles: list[BoardProfile]) -> str:
    """A table of board-type profiles."""
    header = f"{'id':<22} {'family':<13} {'toolchain':<20} {'accelerator':<20} interfaces"
    rows = [header, "-" * len(header)]
    for p in profiles:
        rows.append(
            f"{p.id:<22} {p.family:<13} {p.toolchain:<20} {p.accelerator:<20} "
            f"{','.join(p.interfaces)}"
        )
    rows.append("")
    rows.append("Categorical only. Verify exact specs per board (see each profile's note).")
    return "\n".join(rows) + "\n"
