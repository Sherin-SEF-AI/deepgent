"""jp6 toolchain container: spec resolution, build, and CUDA smoke check.

Builds linux/arm64 images on x86 hosts through qemu binfmt (section 5). The
smoke check is compile-only by design: executing the kernel needs a GPU,
which is golden gt-0001's job on the target board.
"""

import platform
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

import structlog

from deepgent.config import load_versions
from deepgent.errors import ConfigError, ContainerError

_logger = structlog.get_logger(__name__)

_JP6_DIR = Path(__file__).resolve().parent / "jp6"
DOCKERFILE = _JP6_DIR / "Dockerfile"
SMOKE_DIR = _JP6_DIR / "smoke"
SMOKE_SOURCE = "vector_add.cu"

BASE_IMAGE_REPOSITORY = "nvcr.io/nvidia/l4t-jetpack"
IMAGE_REPOSITORY = "deepgent/jp6"
PLATFORM = "linux/arm64"
BINFMT_FLAG = Path("/proc/sys/fs/binfmt_misc/qemu-aarch64")

_ELF_MAGIC = b"\x7fELF"
_ELF_MACHINE_AARCH64 = b"\xb7\x00"  # e_machine little-endian at offset 18


@dataclass(frozen=True)
class Jp6ContainerSpec:
    """jp6 toolchain container parameters, resolved from versions.toml."""

    jetpack: str
    l4t: str
    l4t_container: str
    cuda_arch: str

    @property
    def image_tag(self) -> str:
        return f"{IMAGE_REPOSITORY}:{self.l4t_container}"


def load_jp6_spec(project_root: Path | None = None) -> Jp6ContainerSpec:
    """Read the [jetson.jp6] table into a container spec."""
    versions = load_versions(project_root)
    try:
        jp6 = versions["jetson"]["jp6"]
        return Jp6ContainerSpec(
            jetpack=str(jp6["jetpack"]),
            l4t=str(jp6["l4t"]),
            l4t_container=str(jp6["l4t_container"]),
            cuda_arch=str(jp6["cuda_arch"]),
        )
    except KeyError as exc:
        raise ConfigError(
            f"versions.toml [jetson.jp6] is missing key {exc}; the jp6 container cannot be resolved"
        ) from exc


def elf_is_aarch64(header: bytes) -> bool:
    """True when the given file header is an aarch64 ELF."""
    return header[:4] == _ELF_MAGIC and len(header) >= 20 and header[18:20] == _ELF_MACHINE_AARCH64


class ContainerBuilder:
    """Builds and smoke-checks the jp6 toolchain image."""

    def __init__(self, spec: Jp6ContainerSpec) -> None:
        self._spec = spec

    @property
    def spec(self) -> Jp6ContainerSpec:
        return self._spec

    def preflight(self) -> None:
        """Fail with actionable messages if the host cannot build arm64."""
        if shutil.which("docker") is None:
            raise ContainerError(
                "docker is not on PATH; install Docker Engine "
                "(docs.docker.com/engine/install) to build toolchain containers"
            )
        if platform.machine() not in ("aarch64", "arm64") and not BINFMT_FLAG.exists():
            raise ContainerError(
                "qemu binfmt for aarch64 is not registered; enable it with: "
                "docker run --privileged --rm tonistiigi/binfmt --install arm64"
            )

    def build_command(self) -> list[str]:
        return [
            "docker",
            "build",
            "--platform",
            PLATFORM,
            "--build-arg",
            f"L4T_CONTAINER={self._spec.l4t_container}",
            "-t",
            self._spec.image_tag,
            "-f",
            str(DOCKERFILE),
            str(_JP6_DIR),
        ]

    def build(self) -> None:
        """Build the image, streaming docker output to the caller's stdio."""
        self.preflight()
        command = self.build_command()
        _logger.info("container_build_started", tag=self._spec.image_tag)
        completed = subprocess.run(command, check=False)
        if completed.returncode != 0:
            raise ContainerError(
                f"docker build failed (exit {completed.returncode}) for "
                f"{self._spec.image_tag}; see build output above"
            )
        _logger.info("container_build_finished", tag=self._spec.image_tag)

    def smoke_command(self, out_dir: Path) -> list[str]:
        return [
            "docker",
            "run",
            "--rm",
            "--platform",
            PLATFORM,
            "-v",
            f"{SMOKE_DIR}:/src:ro",
            "-v",
            f"{out_dir}:/out",
            self._spec.image_tag,
            "nvcc",
            f"-arch=sm_{self._spec.cuda_arch}",
            "-o",
            "/out/vector_add",
            f"/src/{SMOKE_SOURCE}",
        ]

    def cuda_smoke(self) -> None:
        """Compile the smoke kernel in-container and verify an aarch64 ELF."""
        self.preflight()
        with tempfile.TemporaryDirectory(prefix="deepgent-smoke-") as tmp:
            out_dir = Path(tmp)
            command = self.smoke_command(out_dir)
            _logger.info("cuda_smoke_started", tag=self._spec.image_tag)
            completed = subprocess.run(command, check=False)
            if completed.returncode != 0:
                raise ContainerError(
                    f"nvcc smoke compile failed (exit {completed.returncode}) "
                    f"in {self._spec.image_tag}; see output above"
                )
            binary = out_dir / "vector_add"
            if not binary.is_file():
                raise ContainerError(
                    "nvcc reported success but produced no binary; the "
                    "container output mount is broken"
                )
            header = binary.read_bytes()[:20]
            if not elf_is_aarch64(header):
                raise ContainerError(
                    f"smoke binary is not an aarch64 ELF; the image was not built for {PLATFORM}"
                )
        _logger.info("cuda_smoke_passed", tag=self._spec.image_tag)
