"""Soak orchestration: schedules, anomaly rules, snapshots, survival report."""

import asyncio
import json
from pathlib import Path
from typing import Any, ClassVar

import pytest

import deepgent.evals.soak as soak_module
from deepgent.boards import BoardConfig, CommandResult, add_board
from deepgent.evals.soak import (
    AnomalyRules,
    SoakPhase,
    SoakRunner,
    check_window,
    default_phases,
)

_HEALTHY = (
    "RAM 3000/30536MB CPU [10%@2201,off] GR3D_FREQ 40%@[1300] "
    "cpu@55.0C tj@62.5C VDD_GPU_SOC 5000mW/4800mW\n"
)
_HOT = (
    "RAM 3000/30536MB CPU [99%@2201,off] GR3D_FREQ 99%@[1300] "
    "cpu@96.0C tj@97.5C VDD_GPU_SOC 21000mW/20000mW\n"
)


class TestRules:
    @pytest.mark.unit
    def test_healthy_window_passes(self) -> None:
        metrics = {"tegrastats_samples": 60.0, "tj_max_c": 62.5}
        assert check_window(metrics, AnomalyRules(), "load-0", 0.0) is None

    @pytest.mark.unit
    def test_thermal_ceiling(self) -> None:
        metrics = {"tegrastats_samples": 60.0, "tj_max_c": 97.5}
        anomaly = check_window(metrics, AnomalyRules(tj_max_c=95.0), "load-0", 0.0)
        assert anomaly is not None and anomaly.rule == "thermal_ceiling"

    @pytest.mark.unit
    def test_telemetry_gap_means_possible_hang(self) -> None:
        anomaly = check_window({"tegrastats_samples": 2.0}, AnomalyRules(), "p", 0.0)
        assert anomaly is not None and anomaly.rule == "telemetry_gap"

    @pytest.mark.unit
    def test_ram_ceiling(self) -> None:
        metrics = {"tegrastats_samples": 60.0, "ram_used_max_mb": 29000.0}
        anomaly = check_window(metrics, AnomalyRules(ram_used_max_mb=28000.0), "p", 0.0)
        assert anomaly is not None and anomaly.rule == "ram_ceiling"


class TestSchedule:
    @pytest.mark.unit
    def test_load_idle_cycling_fills_plan(self) -> None:
        phases = default_phases(3 * 3600.0, "./burn")
        assert sum(p.duration_s for p in phases) == pytest.approx(3 * 3600.0)
        assert phases[0].command == "./burn"
        assert phases[1].command is None  # cool phase
        names = [p.name for p in phases]
        assert "load-0" in names and "cool-0" in names and "load-1" in names

    @pytest.mark.unit
    def test_observation_only(self) -> None:
        phases = default_phases(600.0, None)
        assert phases == [SoakPhase(name="observe", duration_s=600.0)]


class _FakeSoakRunner:
    """Board runner double emitting scripted tegrastats windows."""

    windows: ClassVar[list[str]] = []
    dmesg_calls = 0

    def __init__(self, board: BoardConfig) -> None:
        self._i = 0

    async def __aenter__(self) -> "_FakeSoakRunner":
        return self

    async def __aexit__(self, *args: Any) -> None:
        return None

    async def run(self, command: str, timeout_s: float = 60.0) -> CommandResult:
        if "dmesg" in command:
            _FakeSoakRunner.dmesg_calls += 1
            return CommandResult(command, 0, "kernel: all quiet\n", "", False)
        # Workload command: pretend it ran for the phase and was reaped by
        # the watchdog, the expected end for a continuous burn.
        return CommandResult(command, 124, "", "", True)

    async def capture_tegrastats(self, duration_s: float, interval_ms: int = 500) -> str:
        window = _FakeSoakRunner.windows[min(self._i, len(_FakeSoakRunner.windows) - 1)]
        self._i += 1
        return window


@pytest.fixture
def fake_board(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    (tmp_path / "home").mkdir()
    add_board(
        BoardConfig(
            id="agx-orin",
            host="198.51.100.10",
            ssh_user="nvidia",
            key_path=Path("~/.ssh/k"),
            type="jetson-agx-orin",
        )
    )
    monkeypatch.setattr(soak_module, "BoardRunner", _FakeSoakRunner)
    _FakeSoakRunner.dmesg_calls = 0


class TestSoakRunner:
    @pytest.mark.unit
    def test_survives_healthy_run(self, fake_board: None, tmp_path: Path) -> None:
        _FakeSoakRunner.windows = [_HEALTHY * 60]
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        runner = SoakRunner("agx-orin", run_dir, window_s=0.05)
        phases = [SoakPhase(name="load-0", duration_s=0.1, command="./burn")]
        result = asyncio.run(runner.run(phases))
        assert result.survived
        assert result.phases_completed == ["load-0"]
        assert result.tj_max_c == pytest.approx(62.5)
        assert result.power_max_w == pytest.approx(5.0)
        report = (run_dir / "survival-report.md").read_text()
        assert "RESULT: SURVIVED" in report
        assert json.loads((run_dir / "soak.json").read_text())["survived"] is True

    @pytest.mark.unit
    def test_thermal_anomaly_snapshots_and_stops(self, fake_board: None, tmp_path: Path) -> None:
        _FakeSoakRunner.windows = [_HEALTHY * 60, _HOT * 60]
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        runner = SoakRunner("agx-orin", run_dir, rules=AnomalyRules(tj_max_c=95.0), window_s=0.05)
        phases = [SoakPhase(name="load-0", duration_s=10.0, command="./burn")]
        result = asyncio.run(runner.run(phases))
        assert not result.survived
        assert result.anomaly is not None and result.anomaly.rule == "thermal_ceiling"
        assert result.phases_completed == []
        assert (run_dir / "anomaly-tegrastats.txt").read_text().startswith("RAM")
        assert "all quiet" in (run_dir / "anomaly-dmesg.txt").read_text()
        assert _FakeSoakRunner.dmesg_calls == 1
        assert "RESULT: ANOMALY" in (run_dir / "survival-report.md").read_text()
