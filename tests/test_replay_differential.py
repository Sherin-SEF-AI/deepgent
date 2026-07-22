"""Replay fixtures and differential runs with a fake board runner."""

import asyncio
import json
from pathlib import Path
from typing import Any, ClassVar

import pytest

import deepgent.evals.differential as diff_module
import deepgent.evals.replay as replay_module
from deepgent.boards import BoardConfig, CommandResult, add_board
from deepgent.errors import BoardError
from deepgent.evals.differential import DifferentialRunner, parse_latency_ms
from deepgent.evals.replay import ReplayRecorder, list_fixtures, load_manifest

_TEGRA = (
    "RAM 3000/30536MB CPU [40%@2201,off] GR3D_FREQ 60%@[1300] tj@70.0C VDD_GPU_SOC 8000mW/7500mW\n"
)


@pytest.fixture(autouse=True)
def temp_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    for board_id in ("agx-orin", "pi5-hailo"):
        add_board(
            BoardConfig(
                id=board_id,
                host="198.51.100.10",
                ssh_user="nvidia",
                key_path=Path("~/.ssh/k"),
                type=board_id,
            )
        )
    return tmp_path


class _FakeRunner:
    """Records put/get/run and returns scripted output."""

    stream_bytes: ClassVar[bytes] = b"sensor-stream-payload"
    run_output: ClassVar[str] = "inference done, p99 latency 18.4 ms\n"
    run_exit: ClassVar[int] = 0

    def __init__(self, board: BoardConfig) -> None:
        self.board = board

    async def __aenter__(self) -> "_FakeRunner":
        return self

    async def __aexit__(self, *args: Any) -> None:
        return None

    async def run(self, command: str, timeout_s: float = 60.0) -> CommandResult:
        return CommandResult(command, _FakeRunner.run_exit, _FakeRunner.run_output, "", False)

    async def put(self, local: Path, remote: str) -> None:
        return None

    async def get(self, remote: str, local: Path) -> None:
        Path(local).write_bytes(_FakeRunner.stream_bytes)

    async def capture_tegrastats(self, duration_s: float, interval_ms: int = 500) -> str:
        return _TEGRA * 4


class TestReplay:
    @pytest.mark.unit
    def test_record_writes_fixture_and_manifest(
        self, temp_home: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(replay_module, "BoardRunner", _FakeRunner)
        project = temp_home / "proj"
        project.mkdir()
        recorder = ReplayRecorder("agx-orin", project)
        manifest = asyncio.run(recorder.record("camera-drive", "record.sh", "/tmp/stream.bag"))
        assert manifest.size_bytes == len(_FakeRunner.stream_bytes)
        stored = load_manifest(project, "camera-drive")
        assert stored is not None and stored.sha256 == manifest.sha256
        assert [m.name for m in list_fixtures(project)] == ["camera-drive"]

    @pytest.mark.unit
    def test_replay_verifies_hash(self, temp_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(replay_module, "BoardRunner", _FakeRunner)
        project = temp_home / "proj"
        project.mkdir()
        recorder = ReplayRecorder("agx-orin", project)
        asyncio.run(recorder.record("drive", "record.sh", "/tmp/s.bag"))
        exit_status, output = asyncio.run(recorder.replay("drive", "consume.sh", "/tmp/s.bag"))
        assert exit_status == 0
        assert "latency" in output

    @pytest.mark.unit
    def test_corrupt_fixture_refuses_replay(
        self, temp_home: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(replay_module, "BoardRunner", _FakeRunner)
        project = temp_home / "proj"
        project.mkdir()
        recorder = ReplayRecorder("agx-orin", project)
        asyncio.run(recorder.record("drive", "record.sh", "/tmp/s.bag"))
        (project / ".deepgent" / "fixtures" / "drive" / "stream.bin").write_bytes(b"tampered")
        with pytest.raises(BoardError, match="hash mismatch"):
            asyncio.run(recorder.replay("drive", "consume.sh", "/tmp/s.bag"))

    @pytest.mark.unit
    def test_replay_missing_fixture(self, temp_home: Path) -> None:
        recorder = ReplayRecorder("agx-orin", temp_home / "proj")
        with pytest.raises(BoardError, match="not found"):
            asyncio.run(recorder.replay("ghost", "c.sh", "/tmp/x"))


class TestDifferential:
    @pytest.mark.unit
    def test_latency_parsing(self) -> None:
        assert parse_latency_ms("p99 latency 18.4 ms") == pytest.approx(18.4)
        assert parse_latency_ms("mean: 7 ms over 100 runs") == pytest.approx(7.0)
        assert parse_latency_ms("no numbers here") is None

    @pytest.mark.unit
    def test_runs_across_boards_and_compares(
        self, temp_home: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(diff_module, "BoardRunner", _FakeRunner)
        artifact = temp_home / "detector"
        artifact.write_bytes(b"\x7fELF-fake")
        runner = DifferentialRunner(temp_home)
        result = asyncio.run(
            runner.run(
                artifact,
                ["agx-orin", "pi5-hailo"],
                "./detector --bench",
                costs={"agx-orin": 1999.0, "pi5-hailo": 200.0},
            )
        )
        assert [r.board for r in result.runs] == ["agx-orin", "pi5-hailo"]
        assert all(r.ok for r in result.runs)
        assert result.runs[0].latency_ms == pytest.approx(18.4)
        assert result.runs[0].metrics["power_mean_w"] == pytest.approx(8.0)
        assert result.runs[0].cost_usd == 1999.0
        table = result.render_table()
        assert "agx-orin" in table and "pi5-hailo" in table and "latency_ms" in table

    @pytest.mark.unit
    def test_persist_writes_json_and_table(
        self, temp_home: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(diff_module, "BoardRunner", _FakeRunner)
        artifact = temp_home / "detector"
        artifact.write_bytes(b"x")
        runner = DifferentialRunner(temp_home)
        result = asyncio.run(runner.run(artifact, ["agx-orin"], "./detector"))
        run_dir = temp_home / "out"
        runner.persist(result, run_dir)
        data = json.loads((run_dir / "differential.json").read_text())
        assert data["artifact"] == "detector"
        assert (run_dir / "comparison.txt").read_text().startswith("board")

    @pytest.mark.unit
    def test_missing_artifact(self, temp_home: Path) -> None:
        runner = DifferentialRunner(temp_home)
        with pytest.raises(BoardError, match="does not exist"):
            asyncio.run(runner.run(temp_home / "ghost", ["agx-orin"], "./x"))
