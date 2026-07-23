"""Scaffold integrity tests: packaging metadata, versions manifest, and package layout."""

import importlib
import tomllib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

SUBPACKAGES = [
    "cli",
    "core",
    "agents",
    "hooks",
    "generators",
    "containers",
    "boards",
    "knowledge",
    "evals",
    "telemetry",
    "config",
    "host",
]


@pytest.mark.unit
def test_version_matches_pyproject() -> None:
    import deepgent

    with (REPO_ROOT / "pyproject.toml").open("rb") as f:
        pyproject = tomllib.load(f)
    assert deepgent.__version__ == pyproject["project"]["version"]


@pytest.mark.unit
def test_versions_manifest_is_complete() -> None:
    with (REPO_ROOT / "versions.toml").open("rb") as f:
        versions = tomllib.load(f)

    jp6 = versions["jetson"]["jp6"]
    assert set(jp6) == {
        "jetpack",
        "l4t",
        "cuda",
        "tensorrt",
        "cudnn",
        "l4t_container",
        "cuda_arch",
    }

    jp7 = versions["jetson"]["jp7"]
    assert set(jp7) == {"jetpack", "l4t", "cuda", "tensorrt"}

    ros2 = versions["ros2"]
    assert set(ros2) == {"default", "lts_latest", "jp6_native"}

    assert versions["deepstream"]["version"] == "pinned-per-container"


@pytest.mark.unit
@pytest.mark.parametrize("subpackage", SUBPACKAGES)
def test_subpackage_imports(subpackage: str) -> None:
    module = importlib.import_module(f"deepgent.{subpackage}")
    assert module.__doc__, f"deepgent.{subpackage} must document its layer responsibility"
