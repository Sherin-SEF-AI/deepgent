"""Host detection, auto-configuration, local runner, and generic metrics."""

import asyncio
import tomllib
from pathlib import Path

import pytest

from deepgent.boards import (
    GenericSample,
    LocalRunner,
    load_registry,
    open_runner,
    register_local_target,
    summarize_generic,
)
from deepgent.boards.registry import BoardConfig
from deepgent.host import apply_config, derive_config, detect_host
from deepgent.host.detect import HostProfile, _device_class


def _profile(**overrides: object) -> HostProfile:
    base: dict[str, object] = {
        "os": "Linux",
        "os_version": "26.04",
        "arch": "x86_64",
        "cpu_model": "Test CPU",
        "cpu_count": 8,
        "ram_mb": 32000,
        "python_version": "3.12.0",
        "device_class": "linux-desktop",
        "accelerator": "cuda-discrete",
    }
    base.update(overrides)
    return HostProfile(**base)  # type: ignore[arg-type]


class TestDetection:
    @pytest.mark.unit
    def test_detects_this_machine(self) -> None:
        # Runs against the real host; assert only invariants true everywhere.
        profile = detect_host()
        assert profile.os in ("Linux", "Darwin", "Windows")
        assert profile.cpu_count >= 1
        assert profile.device_class in (
            "jetson",
            "raspberry-pi",
            "linux-desktop",
            "linux-server",
            "macos",
            "windows",
            "unknown",
        )
        assert profile.render()

    @pytest.mark.unit
    def test_device_class_rules(self) -> None:
        assert _device_class("NVIDIA Jetson AGX Orin", "tegra", 30000) == "jetson"
        assert _device_class("Raspberry Pi 5 Model B", "none", 8000) == "raspberry-pi"
        assert _device_class(None, "cuda-discrete", 64000) == "linux-desktop"
        assert _device_class(None, "none", 4000) == "linux-server"

    @pytest.mark.unit
    def test_profile_is_json_serializable(self) -> None:
        import json

        json.dumps(detect_host().to_dict())


class TestAutoConfig:
    @pytest.mark.unit
    def test_jetson_maps_to_jp6(self) -> None:
        config = derive_config(_profile(device_class="jetson", accelerator="tegra"))
        assert config.toolchain == "jp6"
        assert "cuda" in config.capabilities

    @pytest.mark.unit
    def test_desktop_is_native_local(self) -> None:
        config = derive_config(_profile())
        assert config.toolchain == "native"
        assert config.local_execution
        assert "cuda" in config.capabilities

    @pytest.mark.unit
    def test_apply_writes_host_block(self, tmp_path: Path) -> None:
        path = tmp_path / "config.toml"
        apply_config(_profile(), config_path=path)
        data = tomllib.loads(path.read_text())
        assert data["host"]["device_class"] == "linux-desktop"
        assert data["host"]["toolchain"] == "native"
        assert data["default_board"] == "local"

    @pytest.mark.unit
    def test_apply_preserves_operator_keys(self, tmp_path: Path) -> None:
        path = tmp_path / "config.toml"
        path.write_text('default_board = "agx-orin"\n[budget]\nper_task_usd = 5.0\n')
        apply_config(_profile(), config_path=path)
        data = tomllib.loads(path.read_text())
        assert data["default_board"] == "agx-orin"  # not clobbered
        assert data["budget"]["per_task_usd"] == 5.0
        assert data["host"]["device_class"] == "linux-desktop"

    @pytest.mark.unit
    def test_existing_host_block_kept_without_force(self, tmp_path: Path) -> None:
        path = tmp_path / "config.toml"
        apply_config(_profile(device_class="jetson"), config_path=path)
        apply_config(_profile(device_class="linux-desktop"), config_path=path)
        data = tomllib.loads(path.read_text())
        assert data["host"]["device_class"] == "jetson"  # first write wins
        apply_config(_profile(device_class="linux-desktop"), config_path=path, force=True)
        data = tomllib.loads(path.read_text())
        assert data["host"]["device_class"] == "linux-desktop"


class TestLocalTargetAndRunner:
    @pytest.mark.unit
    def test_register_local_target(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("HOME", str(tmp_path))
        register_local_target("linux-desktop", ["cuda", "containers"], "Linux 26.04")
        boards = load_registry()
        assert boards["local"].transport == "local"
        assert boards["local"].device_class == "linux-desktop"

    @pytest.mark.unit
    def test_factory_picks_local_runner(self) -> None:
        local = BoardConfig(id="local", type="linux-desktop", transport="local")
        assert isinstance(open_runner(local), LocalRunner)

    @pytest.mark.unit
    def test_ssh_board_needs_credentials(self) -> None:
        with pytest.raises(ValueError, match="missing host"):
            BoardConfig(id="b", type="jetson", transport="ssh")

    @pytest.mark.unit
    def test_local_runner_runs_commands(self) -> None:
        async def scenario() -> None:
            async with LocalRunner() as runner:
                result = await runner.run("echo deepgent-local")
                assert result.exit_status == 0
                assert "deepgent-local" in result.stdout

        asyncio.run(scenario())

    @pytest.mark.unit
    def test_local_runner_put_get(self, tmp_path: Path) -> None:
        src = tmp_path / "src.bin"
        src.write_bytes(b"payload")
        dest = tmp_path / "out" / "dest.bin"
        pulled = tmp_path / "pulled.bin"

        async def scenario() -> None:
            async with LocalRunner() as runner:
                await runner.put(src, str(dest))
                await runner.get(str(dest), pulled)

        asyncio.run(scenario())
        assert dest.read_bytes() == b"payload"
        assert pulled.read_bytes() == b"payload"

    @pytest.mark.unit
    def test_local_runner_timeout(self) -> None:
        async def scenario() -> None:
            async with LocalRunner() as runner:
                result = await runner.run("sleep 5", timeout_s=0.2)
                assert result.timed_out
                assert result.exit_status == 124

        asyncio.run(scenario())

    @pytest.mark.unit
    def test_local_runner_captures_metrics(self) -> None:
        async def scenario() -> dict[str, float]:
            async with LocalRunner() as runner:
                return await runner.capture_metrics(0.3, interval_ms=100)

        metrics = asyncio.run(scenario())
        assert metrics["samples"] >= 1


class TestGenericMetrics:
    @pytest.mark.unit
    def test_summarize_empty(self) -> None:
        assert summarize_generic([])["samples"] == 0.0

    @pytest.mark.unit
    def test_summarize_with_power_energy(self) -> None:
        samples = [
            GenericSample(
                cpu_pct=50.0,
                ram_used_mb=8000,
                ram_total_mb=32000,
                temp_max_c=60.0,
                gpu_pct=80.0,
                power_w=100.0,
            ),
            GenericSample(
                cpu_pct=70.0,
                ram_used_mb=9000,
                ram_total_mb=32000,
                temp_max_c=65.0,
                gpu_pct=90.0,
                power_w=120.0,
            ),
        ]
        metrics = summarize_generic(samples, interval_ms=1000)
        assert metrics["cpu_max_pct"] == 70.0
        assert metrics["ram_used_max_mb"] == 9000.0
        assert metrics["tj_max_c"] == 65.0
        assert metrics["gr3d_max_pct"] == 90.0
        assert metrics["power_mean_w"] == 110.0
        assert metrics["energy_j"] == pytest.approx(220.0)
