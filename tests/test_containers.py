"""jp6 container spec, build command, and smoke-check plumbing."""

import os
import re
import shutil
import tomllib
from pathlib import Path

import pytest

import deepgent.containers.build as build_module
from deepgent.containers import (
    ContainerBuilder,
    Jp6ContainerSpec,
    elf_is_aarch64,
    load_jp6_spec,
)
from deepgent.errors import ConfigError, ContainerError

REPO_ROOT = Path(__file__).resolve().parent.parent


def _jp6_table() -> dict[str, str]:
    with (REPO_ROOT / "versions.toml").open("rb") as f:
        table: dict[str, str] = tomllib.load(f)["jetson"]["jp6"]
    return table


@pytest.fixture
def spec() -> Jp6ContainerSpec:
    return load_jp6_spec(REPO_ROOT)


class TestSpec:
    @pytest.mark.unit
    def test_spec_matches_versions_toml(self, spec: Jp6ContainerSpec) -> None:
        jp6 = _jp6_table()
        assert spec.jetpack == jp6["jetpack"]
        assert spec.l4t == jp6["l4t"]
        assert spec.l4t_container == jp6["l4t_container"]
        assert spec.cuda_arch == jp6["cuda_arch"]

    @pytest.mark.unit
    def test_image_tag_uses_container_tag(self, spec: Jp6ContainerSpec) -> None:
        assert spec.image_tag == f"deepgent/jp6:{_jp6_table()['l4t_container']}"

    @pytest.mark.unit
    def test_missing_key_raises_config_error(self, tmp_path: Path) -> None:
        (tmp_path / "versions.toml").write_text(
            '[jetson.jp6]\njetpack = "6.2"\n[models]\n[pricing]\n'
        )
        with pytest.raises(ConfigError, match=r"\[jetson\.jp6\] is missing key"):
            load_jp6_spec(tmp_path)


class TestManifest:
    @pytest.mark.unit
    def test_dockerfile_is_fully_parameterized(self) -> None:
        content = build_module.DOCKERFILE.read_text()
        assert "ARG L4T_CONTAINER" in content
        assert "FROM nvcr.io/nvidia/l4t-jetpack:${L4T_CONTAINER}" in content
        # Section 23: never write version strings outside versions.toml.
        assert not re.search(r"r\d+\.\d+", content)

    @pytest.mark.unit
    def test_smoke_kernel_is_a_real_program(self) -> None:
        source = (build_module.SMOKE_DIR / build_module.SMOKE_SOURCE).read_text()
        assert "__global__" in source
        assert "int main()" in source
        assert "cudaMemcpy" in source


class TestBuilderCommands:
    @pytest.mark.unit
    def test_build_command(self, spec: Jp6ContainerSpec) -> None:
        command = ContainerBuilder(spec).build_command()
        assert command[:2] == ["docker", "build"]
        assert command[2:4] == ["--platform", "linux/arm64"]
        assert f"L4T_CONTAINER={spec.l4t_container}" in command
        assert spec.image_tag in command
        assert Path(command[command.index("-f") + 1]).is_file()

    @pytest.mark.unit
    def test_smoke_command(self, spec: Jp6ContainerSpec, tmp_path: Path) -> None:
        command = ContainerBuilder(spec).smoke_command(tmp_path)
        assert command[:3] == ["docker", "run", "--rm"]
        assert "--platform" in command
        assert spec.image_tag in command
        assert f"-arch=sm_{spec.cuda_arch}" in command
        assert command[-1].endswith("vector_add.cu")


class TestPreflight:
    @pytest.mark.unit
    def test_missing_docker_is_actionable(
        self, spec: Jp6ContainerSpec, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(build_module.shutil, "which", lambda _: None)
        with pytest.raises(ContainerError, match="docker is not on PATH"):
            ContainerBuilder(spec).preflight()

    @pytest.mark.unit
    def test_missing_binfmt_is_actionable(
        self, spec: Jp6ContainerSpec, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setattr(build_module.shutil, "which", lambda _: "/usr/bin/docker")
        monkeypatch.setattr(build_module.platform, "machine", lambda: "x86_64")
        monkeypatch.setattr(build_module, "BINFMT_FLAG", tmp_path / "absent")
        with pytest.raises(ContainerError, match="tonistiigi/binfmt"):
            ContainerBuilder(spec).preflight()

    @pytest.mark.unit
    def test_native_arm_needs_no_binfmt(
        self, spec: Jp6ContainerSpec, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setattr(build_module.shutil, "which", lambda _: "/usr/bin/docker")
        monkeypatch.setattr(build_module.platform, "machine", lambda: "aarch64")
        monkeypatch.setattr(build_module, "BINFMT_FLAG", tmp_path / "absent")
        ContainerBuilder(spec).preflight()


class TestElfCheck:
    @pytest.mark.unit
    def test_aarch64_elf_accepted(self) -> None:
        header = b"\x7fELF" + b"\x02\x01\x01" + b"\x00" * 9 + b"\x02\x00" + b"\xb7\x00"
        assert elf_is_aarch64(header)

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "header",
        [
            b"",
            b"\x7fELF",
            b"#!/bin/sh\n" + b"\x00" * 10,
            b"\x7fELF" + b"\x02\x01\x01" + b"\x00" * 9 + b"\x02\x00" + b"\x3e\x00",
        ],
        ids=["empty", "truncated", "script", "x86_64"],
    )
    def test_non_aarch64_rejected(self, header: bytes) -> None:
        assert not elf_is_aarch64(header)


requires_container_env = pytest.mark.skipif(
    shutil.which("docker") is None or os.environ.get("DEEPGENT_CONTAINER_TESTS") != "1",
    reason="needs docker and DEEPGENT_CONTAINER_TESTS=1 (pulls the l4t base image)",
)


@pytest.mark.integration
@requires_container_env
def test_build_and_cuda_smoke_end_to_end() -> None:
    builder = ContainerBuilder(load_jp6_spec(REPO_ROOT))
    builder.build()
    builder.cuda_smoke()
