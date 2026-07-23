"""Board leases and the board-farm MCP tool set (with a fake SSH runner)."""

import asyncio
import json
import time
from pathlib import Path
from typing import Any, ClassVar

import pytest

import deepgent.boards.farm as farm_module
import deepgent.boards.leases as leases_module
from deepgent.boards import (
    BoardConfig,
    CommandResult,
    acquire_lease,
    add_board,
    build_board_farm_tools,
    current_lease,
    release_lease,
    require_lease,
)
from deepgent.errors import BoardError

_TEGRASTATS_LINE = "RAM 2048/30536MB CPU [3%@729,off] GR3D_FREQ 57%@[1300,1297]\n"


@pytest.fixture(autouse=True)
def temp_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("HOME", str(tmp_path))
    return tmp_path


@pytest.fixture
def registered_board() -> BoardConfig:
    board = BoardConfig(
        id="agx-orin",
        host="198.51.100.10",
        ssh_user="nvidia",
        key_path=Path("~/.ssh/test_board_key"),
        type="jetson-agx-orin",
    )
    add_board(board)
    return board


class FakeRunner:
    """Stands in for BoardRunner; records calls, no network."""

    calls: ClassVar[list[tuple[str, Any]]] = []

    def __init__(self, board: BoardConfig) -> None:
        self._board = board

    async def __aenter__(self) -> "FakeRunner":
        return self

    async def __aexit__(self, *args: Any) -> None:
        return None

    async def run(self, command: str, timeout_s: float = 60.0) -> CommandResult:
        FakeRunner.calls.append(("run", command))
        return CommandResult(
            command=command, exit_status=0, stdout="aarch64\n", stderr="", timed_out=False
        )

    async def put(self, local: Path, remote: str) -> None:
        FakeRunner.calls.append(("put", (str(local), remote)))

    async def capture_metrics(self, duration_s: float, interval_ms: int = 500) -> dict[str, float]:
        FakeRunner.calls.append(("metrics", duration_s))
        from deepgent.boards import parse_capture

        return parse_capture(_TEGRASTATS_LINE * 6).summary_metrics(interval_ms=interval_ms)


@pytest.fixture
def tools(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    FakeRunner.calls = []
    monkeypatch.setattr(farm_module, "open_runner", lambda board: FakeRunner(board))
    return {t.name: t for t in build_board_farm_tools(holder="holder-test")}


def _call(tools: dict[str, Any], name: str, args: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = asyncio.run(tools[name].handler(args))
    return result


def _payload(result: dict[str, Any]) -> Any:
    return json.loads(result["content"][0]["text"])


class TestLeases:
    @pytest.mark.unit
    def test_acquire_release_round_trip(self) -> None:
        lease = acquire_lease("agx-orin", "holder-a", ttl_s=60)
        assert current_lease("agx-orin") == lease
        release_lease("agx-orin", "holder-a")
        assert current_lease("agx-orin") is None

    @pytest.mark.unit
    def test_contention_rejected(self) -> None:
        acquire_lease("agx-orin", "holder-a", ttl_s=60)
        with pytest.raises(BoardError, match="leased by holder-a"):
            acquire_lease("agx-orin", "holder-b", ttl_s=60)

    @pytest.mark.unit
    def test_expired_lease_is_reclaimable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        acquire_lease("agx-orin", "holder-a", ttl_s=60)
        future = time.time() + 120
        monkeypatch.setattr(leases_module.time, "time", lambda: future)
        lease = acquire_lease("agx-orin", "holder-b", ttl_s=60)
        assert lease.holder == "holder-b"

    @pytest.mark.unit
    def test_release_requires_holder(self) -> None:
        acquire_lease("agx-orin", "holder-a", ttl_s=60)
        with pytest.raises(BoardError, match="refusing to release"):
            release_lease("agx-orin", "holder-b")

    @pytest.mark.unit
    def test_require_lease(self) -> None:
        with pytest.raises(BoardError, match="requires an active lease"):
            require_lease("agx-orin", "holder-a")
        acquire_lease("agx-orin", "holder-a", ttl_s=60)
        assert require_lease("agx-orin", "holder-a").holder == "holder-a"


class TestFarmTools:
    @pytest.mark.unit
    def test_tool_names_match_safety_gate_expectations(self, tools: dict[str, Any]) -> None:
        assert set(tools) == {
            "list_boards",
            "lease",
            "release",
            "deploy",
            "exec",
            "capture_metrics",
            "power",
        }

    @pytest.mark.unit
    def test_list_boards(self, tools: dict[str, Any], registered_board: BoardConfig) -> None:
        payload = _payload(_call(tools, "list_boards", {}))
        assert payload["boards"][0]["id"] == "agx-orin"
        assert payload["boards"][0]["leased_by"] is None

    @pytest.mark.unit
    def test_mutating_tools_require_lease(
        self, tools: dict[str, Any], registered_board: BoardConfig, tmp_path: Path
    ) -> None:
        artifact = tmp_path / "bin"
        artifact.write_bytes(b"x")
        for name, args in [
            ("exec", {"board": "agx-orin", "command": "uname -m", "timeout_s": 10}),
            (
                "deploy",
                {"board": "agx-orin", "local_path": str(artifact), "remote_path": "/tmp/bin"},
            ),
            ("capture_metrics", {"board": "agx-orin", "duration_s": 5}),
        ]:
            result = _call(tools, name, args)
            assert result.get("is_error") is True, name
            assert "lease" in result["content"][0]["text"]

    @pytest.mark.unit
    def test_lease_then_exec_and_metrics(
        self, tools: dict[str, Any], registered_board: BoardConfig
    ) -> None:
        lease_result = _payload(_call(tools, "lease", {"board": "agx-orin"}))
        assert lease_result["holder"] == "holder-test"

        exec_result = _payload(
            _call(tools, "exec", {"board": "agx-orin", "command": "uname -m", "timeout_s": 10})
        )
        assert exec_result["exit_status"] == 0
        assert "aarch64" in exec_result["stdout"]

        metrics = _payload(_call(tools, "capture_metrics", {"board": "agx-orin", "duration_s": 5}))
        assert metrics["metrics"]["tegrastats_samples"] == 6.0

        release = _call(tools, "release", {"board": "agx-orin"})
        assert release.get("is_error") is None
        assert current_lease("agx-orin") is None

    @pytest.mark.unit
    def test_unknown_board_is_actionable(self, tools: dict[str, Any]) -> None:
        result = _call(tools, "lease", {"board": "ghost"})
        assert result.get("is_error") is True
        assert "deepgent boards add" in result["content"][0]["text"]

    @pytest.mark.unit
    def test_power_without_hardware_refuses_honestly(
        self, tools: dict[str, Any], registered_board: BoardConfig
    ) -> None:
        _call(tools, "lease", {"board": "agx-orin"})
        result = _call(tools, "power", {"board": "agx-orin", "action": "cycle"})
        assert result.get("is_error") is True
        assert "power_ctl=none" in result["content"][0]["text"]
