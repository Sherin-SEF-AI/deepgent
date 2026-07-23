"""Environment diagnostics shared by `deepgent doctor` and the GUI dashboard.

Each check is a pure, side-effect-free probe returning a typed result, so
both the CLI and the GUI render the same truth from one source.
"""

import importlib.metadata
import platform
import shutil
import sys
from dataclasses import dataclass

from deepgent.config import load_settings
from deepgent.containers.build import BINFMT_FLAG
from deepgent.errors import DeepgentError
from deepgent.host.detect import HostProfile, detect_host


@dataclass(frozen=True)
class Check:
    """One environment check result."""

    name: str
    ok: bool
    detail: str


def run_checks(profile: HostProfile | None = None) -> list[Check]:
    """Run every environment check and return structured results."""
    host = profile if profile is not None else detect_host()
    checks: list[Check] = [
        Check(
            "host",
            True,
            f"{host.device_class} / {host.arch} / accel={host.accelerator}",
        )
    ]

    py = sys.version_info
    checks.append(
        Check("python", py >= (3, 12), f"{py.major}.{py.minor}.{py.micro} (need >= 3.12)")
    )

    uv_path = shutil.which("uv")
    checks.append(
        Check("uv", uv_path is not None, uv_path or "not on PATH; install from astral.sh/uv")
    )

    docker_path = shutil.which("docker")
    checks.append(
        Check(
            "docker",
            docker_path is not None,
            docker_path or "not on PATH; install Docker Engine (docs.docker.com/engine/install)",
        )
    )

    native_arm = platform.machine() in ("aarch64", "arm64")
    binfmt_ok = native_arm or BINFMT_FLAG.exists()
    if native_arm:
        binfmt_detail = "native arm64 host"
    elif binfmt_ok:
        binfmt_detail = str(BINFMT_FLAG)
    else:
        binfmt_detail = (
            "not registered; run: docker run --privileged --rm tonistiigi/binfmt --install arm64"
        )
    checks.append(Check("qemu binfmt (arm64)", binfmt_ok, binfmt_detail))

    try:
        settings = load_settings()
    except DeepgentError as exc:
        checks.append(Check("versions.toml", False, str(exc)))
    else:
        checks.append(
            Check(
                "versions.toml",
                True,
                f"model tiers: opus={settings.models.opus}, "
                f"sonnet={settings.models.sonnet}, haiku={settings.models.haiku}",
            )
        )

    try:
        sdk_version = importlib.metadata.version("claude-agent-sdk")
    except importlib.metadata.PackageNotFoundError:
        checks.append(Check("claude-agent-sdk", False, "not installed; run uv sync"))
    else:
        checks.append(Check("claude-agent-sdk", True, sdk_version))

    import os

    has_key = bool(os.environ.get("ANTHROPIC_API_KEY"))
    checks.append(
        Check(
            "api key",
            has_key,
            "ANTHROPIC_API_KEY is set"
            if has_key
            else "ANTHROPIC_API_KEY is not set; export it or configure the OS keyring",
        )
    )
    return checks
