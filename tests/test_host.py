"""Host detection, auto-config, local runner, generic metrics, and the CLI
host surface. One test per capability-inventory item, including failure paths
(asserting the exact message and exit code, not only happy paths)."""

import asyncio
import json
import os
import tomllib
from pathlib import Path

import pytest
from typer.testing import CliRunner

import deepgent.host.detect as detect_module
from deepgent.boards import (
    GenericSample,
    LocalRunner,
    load_registry,
    open_runner,
    register_local_target,
    summarize_generic,
)
from deepgent.boards.registry import BoardConfig
from deepgent.cli import app
from deepgent.config import load_settings
from deepgent.errors import ConfigError
from deepgent.host import (
    DETECTOR_VERSION,
    apply_config,
    derive_config,
    detect_host,
    is_valid_device_class,
    pin_host_override,
)
from deepgent.host.detect import HostProfile, ResourceLimits, _device_class

REPO_ROOT = Path(__file__).resolve().parent.parent
runner = CliRunner()


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
        "detected_at": 1000.0,
    }
    base.update(overrides)
    return HostProfile(**base)  # type: ignore[arg-type]


# ---------------------------------------------------------------- detection


class TestDetection:
    @pytest.mark.unit
    def test_detects_this_machine(self) -> None:
        profile = detect_host(now=1234.0)
        assert profile.os in ("Linux", "Darwin", "Windows")
        assert profile.cpu_count >= 1
        assert is_valid_device_class(profile.device_class)
        assert profile.detected_at == 1234.0
        assert profile.detector_version == DETECTOR_VERSION
        assert profile.render()

    @pytest.mark.unit
    def test_profile_is_json_serializable(self) -> None:
        json.dumps(detect_host().to_dict(), default=str)

    @pytest.mark.unit
    @pytest.mark.parametrize(
        ("model", "accel", "ram", "container", "expected"),
        [
            ("NVIDIA Jetson AGX Orin", "tegra", 30000, False, "jetson"),
            ("Raspberry Pi 5 Model B", "none", 8000, False, "raspberry-pi"),
            (None, "cuda-discrete", 64000, False, "linux-desktop"),
            (None, "multi-gpu", 64000, False, "linux-desktop"),
            (None, "none", 4000, False, "linux-server"),
            (None, "none", 8000, True, "container"),
        ],
    )
    def test_device_class_rules(
        self, model: str | None, accel: str, ram: int, container: bool, expected: str
    ) -> None:
        assert _device_class(model, accel, ram, container) == expected  # type: ignore[arg-type]

    @pytest.mark.unit
    def test_wsl_detected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            detect_module,
            "_read_text",
            lambda p: "5.15.0-microsoft-standard-WSL2" if "osrelease" in p else None,
        )
        assert detect_module._is_wsl()

    @pytest.mark.unit
    def test_container_detected_via_dockerenv(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(detect_module.Path, "exists", lambda self: str(self) == "/.dockerenv")
        assert detect_module._is_container()

    @pytest.mark.unit
    def test_no_network_in_detection(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Item 41: detection must never open a socket.
        import socket

        def _boom(*a: object, **k: object) -> None:
            raise AssertionError("detection made a network call")

        monkeypatch.setattr(socket.socket, "connect", _boom)
        detect_host()

    @pytest.mark.unit
    def test_survives_no_proc(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Item 20: no /proc, no /sys, no probes: nulls, not a crash.
        monkeypatch.setattr(detect_module, "_read_text", lambda p: None)
        monkeypatch.setattr(detect_module.shutil, "which", lambda n: None)
        monkeypatch.setattr(detect_module.Path, "exists", lambda self: False)
        monkeypatch.setattr(detect_module.Path, "is_file", lambda self: False)
        profile = detect_host()
        assert profile.ram_mb is None
        assert profile.cpu_model is None or isinstance(profile.cpu_model, str)
        assert is_valid_device_class(profile.device_class)

    @pytest.mark.unit
    def test_truncation_adds_note(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Item 37: exceeding the probe budget records a note, not a crash.
        def _truncating_gpus(budget: object, notes: list[str]) -> tuple[list[object], str]:
            budget.truncated = True  # type: ignore[attr-defined]
            return [], "none"

        monkeypatch.setattr(detect_module, "_detect_gpus", _truncating_gpus)
        profile = detect_host()
        assert any("truncated" in n for n in profile.notes)


class TestGpuProbe:
    @pytest.mark.unit
    def test_nvidia_multi_gpu_class(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(detect_module.shutil, "which", lambda n: "/usr/bin/nvidia-smi")
        monkeypatch.setattr(
            detect_module,
            "_run",
            lambda cmd, budget=None: "RTX 5080, 16303\nRTX 4090, 24564\n",
        )
        budget = detect_module._ProbeBudget(deadline=detect_module.time.monotonic() + 30)
        gpus, accel = detect_module._detect_gpus(budget, [])
        assert accel == "multi-gpu"
        assert len(gpus) == 2

    @pytest.mark.unit
    def test_nvidia_present_but_failing_adds_note(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(detect_module.shutil, "which", lambda n: "/usr/bin/nvidia-smi")
        monkeypatch.setattr(detect_module, "_run", lambda cmd, budget=None: None)
        notes: list[str] = []
        budget = detect_module._ProbeBudget(deadline=detect_module.time.monotonic() + 30)
        gpus = detect_module._nvidia_gpus(budget, notes)
        assert gpus == []
        assert any("driver" in n for n in notes)

    @pytest.mark.unit
    def test_nvidia_no_devices_line(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(detect_module.shutil, "which", lambda n: "/usr/bin/nvidia-smi")
        monkeypatch.setattr(detect_module, "_run", lambda cmd, budget=None: "No devices found\n")
        notes: list[str] = []
        budget = detect_module._ProbeBudget(deadline=detect_module.time.monotonic() + 30)
        assert detect_module._nvidia_gpus(budget, notes) == []
        assert any("no cuda devices" in n.lower() for n in notes)

    @pytest.mark.unit
    def test_probe_budget_truncates(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(detect_module.shutil, "which", lambda n: "/usr/bin/rocminfo")
        budget = detect_module._ProbeBudget(deadline=detect_module.time.monotonic() - 1)
        assert detect_module._run(["rocminfo"], budget) is None
        assert budget.truncated


class TestCgroupLimits:
    @pytest.mark.unit
    def test_cgroup_v2_cpu_and_mem(self, monkeypatch: pytest.MonkeyPatch) -> None:
        values = {
            "/sys/fs/cgroup/cpu.max": "200000 100000",  # 2 cores
            "/sys/fs/cgroup/memory.max": str(4 * 1024 * 1024 * 1024),  # 4 GiB
        }
        monkeypatch.setattr(detect_module, "_read_text", lambda p: values.get(p))
        limits = detect_module._cgroup_limits()
        assert limits.cpu_effective == pytest.approx(2.0)
        assert limits.ram_limit_mb == 4096

    @pytest.mark.unit
    def test_cgroup_unlimited_is_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            detect_module,
            "_read_text",
            lambda p: "max 100000" if "cpu.max" in p else "max",
        )
        limits = detect_module._cgroup_limits()
        assert limits.cpu_effective is None
        assert limits.ram_limit_mb is None


# --------------------------------------------------------------- auto-config


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
    def test_windows_not_local_executor(self) -> None:
        config = derive_config(_profile(os="Windows", device_class="windows"))
        assert not config.local_execution

    @pytest.mark.unit
    def test_apply_writes_host_block(self, tmp_path: Path) -> None:
        path = tmp_path / "config.toml"
        _, written = apply_config(_profile(), config_path=path)
        assert written is True
        data = tomllib.loads(path.read_text())
        assert data["host"]["device_class"] == "linux-desktop"
        assert data["host"]["toolchain"] == "native"
        assert data["host"]["detector_version"] == DETECTOR_VERSION
        assert data["host"]["detected_at"] == 1000.0
        assert data["default_board"] == "local"

    @pytest.mark.unit
    def test_apply_preserves_operator_keys(self, tmp_path: Path) -> None:
        path = tmp_path / "config.toml"
        path.write_text('default_board = "agx-orin"\n[budget]\nper_task_usd = 5.0\n')
        apply_config(_profile(), config_path=path)
        data = tomllib.loads(path.read_text())
        assert data["default_board"] == "agx-orin"
        assert data["budget"]["per_task_usd"] == 5.0
        assert data["host"]["device_class"] == "linux-desktop"

    @pytest.mark.unit
    def test_existing_host_block_kept_without_force(self, tmp_path: Path) -> None:
        path = tmp_path / "config.toml"
        _, first = apply_config(_profile(device_class="jetson"), config_path=path)
        _, second = apply_config(_profile(device_class="linux-desktop"), config_path=path)
        assert first is True and second is False
        assert tomllib.loads(path.read_text())["host"]["device_class"] == "jetson"
        _, forced = apply_config(
            _profile(device_class="linux-desktop"), config_path=path, force=True
        )
        assert forced is True
        assert tomllib.loads(path.read_text())["host"]["device_class"] == "linux-desktop"

    @pytest.mark.unit
    def test_pinned_block_never_overwritten_even_with_force(self, tmp_path: Path) -> None:
        path = tmp_path / "config.toml"
        pin_host_override(path, device_class="jetson")
        _, written = apply_config(
            _profile(device_class="linux-desktop"), config_path=path, force=True
        )
        assert written is False
        assert tomllib.loads(path.read_text())["host"]["device_class"] == "jetson"

    @pytest.mark.unit
    def test_corrupt_toml_is_actionable(self, tmp_path: Path) -> None:
        path = tmp_path / "config.toml"
        path.write_text("this is = = not toml [[[")
        with pytest.raises(ConfigError, match="not valid TOML"):
            apply_config(_profile(), config_path=path)

    @pytest.mark.unit
    def test_unwritable_path_is_actionable(self, tmp_path: Path) -> None:
        # A file where a directory is expected makes the parent unwritable.
        blocker = tmp_path / "blocker"
        blocker.write_text("x")
        target = blocker / "config.toml"
        with pytest.raises(ConfigError, match="cannot write host config"):
            apply_config(_profile(), config_path=target)

    @pytest.mark.unit
    def test_atomic_write_leaves_no_temp(self, tmp_path: Path) -> None:
        path = tmp_path / "config.toml"
        apply_config(_profile(), config_path=path)
        leftovers = [p.name for p in tmp_path.iterdir() if p.name.startswith(".config-")]
        assert leftovers == []

    @pytest.mark.unit
    def test_pin_rejects_invalid_class(self, tmp_path: Path) -> None:
        with pytest.raises(ConfigError, match="is not a valid device class"):
            pin_host_override(tmp_path / "config.toml", device_class="teapot")


# ------------------------------------------------------------ typed settings


class TestHostSettings:
    @pytest.mark.unit
    def test_host_block_round_trips(self, tmp_path: Path) -> None:
        import shutil

        project = tmp_path / "proj"
        (project / ".deepgent").mkdir(parents=True)
        shutil.copy(REPO_ROOT / "versions.toml", project / "versions.toml")
        (project / ".deepgent" / "config.toml").write_text(
            '[host]\ndevice_class = "linux-desktop"\ntoolchain = "native"\n'
            'capabilities = ["cuda"]\n'
        )
        settings = load_settings(project)
        assert settings.host.device_class == "linux-desktop"
        assert settings.host.capabilities == ["cuda"]

    @pytest.mark.unit
    def test_env_override_reaches_settings(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DEEPGENT_HOST__DEVICE_CLASS", "raspberry-pi")
        settings = load_settings(REPO_ROOT)
        assert settings.host.device_class == "raspberry-pi"


# ------------------------------------------------------- local target/runner


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
    def test_registry_unwritable_is_actionable(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Item 26: a registry path that cannot be written yields an
        # actionable BoardError, not a raw OSError.
        from deepgent.errors import BoardError

        blocker = tmp_path / "blocker"
        blocker.write_text("x")
        import deepgent.boards.registry as registry_module

        monkeypatch.setattr(registry_module, "registry_path", lambda: blocker / "boards.toml")
        with pytest.raises(BoardError, match="cannot write board registry"):
            register_local_target("linux-desktop", [], "Linux")

    @pytest.mark.unit
    def test_ssh_board_needs_credentials(self) -> None:
        with pytest.raises(ValueError, match="missing host"):
            BoardConfig(id="b", type="jetson", transport="ssh")

    @pytest.mark.unit
    def test_local_runner_runs_commands(self) -> None:
        async def scenario() -> None:
            async with LocalRunner() as r:
                result = await r.run("echo deepgent-local")
                assert result.exit_status == 0
                assert "deepgent-local" in result.stdout

        asyncio.run(scenario())

    @pytest.mark.unit
    def test_local_runner_nonzero_exit(self) -> None:
        async def scenario() -> None:
            async with LocalRunner() as r:
                result = await r.run("exit 7")
                assert result.exit_status == 7
                assert not result.timed_out

        asyncio.run(scenario())

    @pytest.mark.unit
    def test_local_runner_put_get(self, tmp_path: Path) -> None:
        src = tmp_path / "src.bin"
        src.write_bytes(b"payload")
        dest = tmp_path / "out" / "dest.bin"
        pulled = tmp_path / "pulled.bin"

        async def scenario() -> None:
            async with LocalRunner() as r:
                await r.put(src, str(dest))
                await r.get(str(dest), pulled)

        asyncio.run(scenario())
        assert dest.read_bytes() == b"payload"
        assert pulled.read_bytes() == b"payload"

    @pytest.mark.unit
    def test_local_runner_get_missing(self, tmp_path: Path) -> None:
        from deepgent.errors import BoardError

        async def scenario() -> None:
            async with LocalRunner() as r:
                await r.get(str(tmp_path / "ghost"), tmp_path / "x")

        with pytest.raises(BoardError, match="does not exist"):
            asyncio.run(scenario())

    @pytest.mark.unit
    def test_local_runner_timeout_kills_group(self, tmp_path: Path) -> None:
        marker = tmp_path / "still-alive"
        # A child that outlives its parent shell writes the marker after the
        # timeout; a correct process-group kill prevents that write.
        script = f"(sleep 2 && touch {marker}) & sleep 5"

        async def scenario() -> None:
            async with LocalRunner() as r:
                result = await r.run(script, timeout_s=0.3)
                assert result.timed_out
                assert result.exit_status == 124

        asyncio.run(scenario())
        # Give any escaped child time to fire, then assert it did not.
        import time as _time

        _time.sleep(2.5)
        assert not marker.exists(), "child survived the process-group kill"

    @pytest.mark.unit
    def test_local_runner_cancellation_terminates_child(self, tmp_path: Path) -> None:
        marker = tmp_path / "cancel-alive"
        script = f"(sleep 2 && touch {marker}) & sleep 5"

        async def scenario() -> None:
            async with LocalRunner() as r:
                task = asyncio.ensure_future(r.run(script, timeout_s=30))
                await asyncio.sleep(0.3)
                task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await task

        asyncio.run(scenario())
        import time as _time

        _time.sleep(2.5)
        assert not marker.exists(), "child survived task cancellation"

    @pytest.mark.unit
    def test_local_runner_captures_metrics(self) -> None:
        async def scenario() -> dict[str, float]:
            async with LocalRunner() as r:
                return await r.capture_metrics(0.3, interval_ms=100)

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


# --------------------------------------------------------------- CLI surface


class TestCliHostSurface:
    @pytest.fixture(autouse=True)
    def _home(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        home = tmp_path / "home"
        home.mkdir()
        monkeypatch.setenv("HOME", str(home))
        monkeypatch.chdir(REPO_ROOT)

    @pytest.mark.unit
    def test_setup_writes_and_registers(self) -> None:
        result = runner.invoke(app, ["setup"])
        assert result.exit_code == 0, result.output
        assert "configured:" in result.output
        assert "registered target 'local'" in result.output
        assert load_registry()["local"].transport == "local"

    @pytest.mark.unit
    def test_setup_dry_run_writes_nothing(self, tmp_path: Path) -> None:
        result = runner.invoke(app, ["setup", "--dry-run"])
        assert result.exit_code == 0
        assert "dry run: nothing written" in result.output
        assert not (Path(os.environ["HOME"]) / ".deepgent" / "config.toml").exists()
        assert "local" not in load_registry()

    @pytest.mark.unit
    def test_setup_json(self) -> None:
        result = runner.invoke(app, ["setup", "--json"])
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert "profile" in payload and "config" in payload
        assert payload["config"]["toolchain"] in ("native", "jp6")

    @pytest.mark.unit
    def test_setup_second_run_keeps_config(self) -> None:
        runner.invoke(app, ["setup"])
        result = runner.invoke(app, ["setup"])
        assert result.exit_code == 0
        assert "already present" in result.output

    @pytest.mark.unit
    def test_setup_force_refreshes(self) -> None:
        runner.invoke(app, ["setup"])
        result = runner.invoke(app, ["setup", "--force"])
        assert result.exit_code == 0
        assert "wrote" in result.output

    @pytest.mark.unit
    def test_setup_invalid_env_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DEEPGENT_HOST__DEVICE_CLASS", "teapot")
        result = runner.invoke(app, ["setup"])
        assert result.exit_code == 1
        assert "not a valid device class" in result.output

    @pytest.mark.unit
    def test_setup_valid_env_override_pins(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DEEPGENT_HOST__DEVICE_CLASS", "raspberry-pi")
        result = runner.invoke(app, ["setup"])
        assert result.exit_code == 0
        assert "pinned host override" in result.output
        config = Path(os.environ["HOME"]) / ".deepgent" / "config.toml"
        data = tomllib.loads(config.read_text())
        assert data["host"]["pinned"] is True
        assert data["host"]["device_class"] == "raspberry-pi"

    @pytest.mark.unit
    def test_host_show(self) -> None:
        result = runner.invoke(app, ["host"])
        assert result.exit_code == 0
        assert "host profile" in result.output
        # host show must not write config
        assert not (Path(os.environ["HOME"]) / ".deepgent" / "config.toml").exists()

    @pytest.mark.unit
    def test_host_show_json(self) -> None:
        result = runner.invoke(app, ["host", "--json"])
        assert result.exit_code == 0
        profile = json.loads(result.output)
        assert "device_class" in profile and "accelerator" in profile

    @pytest.mark.unit
    def test_doctor_json(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
        result = runner.invoke(app, ["doctor", "--json"])
        payload = json.loads(result.output)
        assert "checks" in payload
        assert any(c["name"] == "host" for c in payload["checks"])


def test_resource_limits_default() -> None:
    # ResourceLimits is a plain dataclass used across the profile.
    assert ResourceLimits(cpu_effective=None, ram_limit_mb=None).cpu_effective is None
