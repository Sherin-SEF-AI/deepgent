"""Board registry, watchdog wrapping, and tegrastats parsing."""

from pathlib import Path

import pytest

from deepgent.boards import (
    BoardConfig,
    add_board,
    get_board,
    load_registry,
    parse_capture,
    parse_line,
    remove_board,
    watchdog_command,
)
from deepgent.errors import BoardError

# Realistic L4T r36-family tegrastats lines.
_LINE_FULL = (
    "11-14-2024 12:34:56 RAM 3162/30536MB (lfb 6x4MB) SWAP 0/15268MB (cached 0MB) "
    "CPU [12%@2201,4%@2201,0%@729,1%@729,off,off,off,off,off,off,off,off] "
    "EMC_FREQ 1%@2133 GR3D_FREQ 43%@[1300] VIC_FREQ 115 APE 174 "
    "cpu@47.968C soc2@46.375C soc0@46.906C gpu@48.343C tj@49.968C soc1@46.687C "
    "VDD_GPU_SOC 3175mW/3175mW VDD_CPU_CV 794mW/794mW"
)
_LINE_MINIMAL = "RAM 1000/30536MB CPU [5%@729,off] GR3D_FREQ 0%@[305]"


@pytest.fixture
def temp_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("HOME", str(tmp_path))
    return tmp_path


def _board(board_id: str = "agx-orin") -> BoardConfig:
    return BoardConfig(
        id=board_id,
        host="198.51.100.10",
        ssh_user="nvidia",
        key_path=Path("~/.ssh/test_board_key"),
        type="jetson-agx-orin",
        l4t="36.4.3",
        capabilities=["csi", "gpio"],
    )


class TestRegistry:
    @pytest.mark.unit
    def test_empty_registry(self, temp_home: Path) -> None:
        assert load_registry() == {}

    @pytest.mark.unit
    def test_add_load_round_trip(self, temp_home: Path) -> None:
        add_board(_board())
        loaded = get_board("agx-orin")
        assert loaded == _board()
        assert (temp_home / ".deepgent" / "boards.toml").is_file()

    @pytest.mark.unit
    def test_duplicate_add_rejected(self, temp_home: Path) -> None:
        add_board(_board())
        with pytest.raises(BoardError, match="already exists"):
            add_board(_board())

    @pytest.mark.unit
    def test_remove(self, temp_home: Path) -> None:
        add_board(_board())
        remove_board("agx-orin")
        assert load_registry() == {}
        with pytest.raises(BoardError, match="not registered"):
            remove_board("agx-orin")

    @pytest.mark.unit
    def test_unknown_board_is_actionable(self, temp_home: Path) -> None:
        with pytest.raises(BoardError, match="deepgent boards add"):
            get_board("missing-board")

    @pytest.mark.unit
    def test_key_path_expansion(self) -> None:
        board = _board()
        assert "~" not in str(board.expanded_key_path)


class TestWatchdog:
    @pytest.mark.unit
    def test_wraps_with_remote_timeout(self) -> None:
        wrapped = watchdog_command("./vector_add --runs 3", 45.0)
        assert wrapped.startswith("timeout --kill-after=5 45 bash -c ")
        assert "'./vector_add --runs 3'" in wrapped

    @pytest.mark.unit
    def test_quotes_hostile_commands(self) -> None:
        wrapped = watchdog_command("echo 'a b'; ls", 10)
        assert "bash -c 'echo '\"'\"'a b'\"'\"'; ls'" in wrapped


class TestTegrastatsParser:
    @pytest.mark.unit
    def test_full_line(self) -> None:
        sample = parse_line(_LINE_FULL)
        assert sample is not None
        assert sample.ram_used_mb == 3162
        assert sample.ram_total_mb == 30536
        assert sample.gr3d_pct == 43
        assert sample.cpu_pcts[:4] == (12, 4, 0, 1)
        assert sample.cpu_pcts[4] is None  # "off" core
        assert sample.temps_c["tj"] == pytest.approx(49.968)
        assert sample.temps_c["gpu"] == pytest.approx(48.343)

    @pytest.mark.unit
    def test_minimal_line(self) -> None:
        sample = parse_line(_LINE_MINIMAL)
        assert sample is not None
        assert sample.ram_used_mb == 1000
        assert sample.gr3d_pct == 0
        assert sample.temps_c == {}

    @pytest.mark.unit
    def test_jp6_dual_gpc_gr3d_format(self) -> None:
        # JP6 consolidates GPU load into one entry with per-GPC frequencies:
        # GR3D_FREQ X%@[F1,F2] (r36 TegrastatsUtility docs).
        sample = parse_line("RAM 2048/30536MB CPU [3%@729,off] GR3D_FREQ 57%@[1300,1297]")
        assert sample is not None
        assert sample.gr3d_pct == 57

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "line",
        ["", "not tegrastats output", "error: tegrastats requires root"],
    )
    def test_garbage_is_skipped_not_misparsed(self, line: str) -> None:
        assert parse_line(line) is None

    @pytest.mark.unit
    def test_capture_summary(self) -> None:
        text = "\n".join([_LINE_FULL, _LINE_MINIMAL, "garbage line", ""])
        capture = parse_capture(text)
        assert len(capture.samples) == 2
        assert capture.skipped_lines == 1
        metrics = capture.summary_metrics()
        assert metrics["tegrastats_samples"] == 2.0
        assert metrics["ram_used_max_mb"] == 3162.0
        assert metrics["gr3d_max_pct"] == 43.0
        assert metrics["tj_max_c"] == pytest.approx(49.968)

    @pytest.mark.unit
    def test_empty_capture(self) -> None:
        capture = parse_capture("")
        assert capture.summary_metrics()["tegrastats_samples"] == 0.0
