"""Shadow-mode field-replay diffing (#9).

Diff logic is pure and tested directly; the replay path uses a ReplayRecorder
double so no board is required.
"""

import asyncio
import json
from pathlib import Path
from typing import ClassVar

import pytest

import deepgent.evals.shadow as shadow_module
from deepgent.evals.shadow import (
    ShadowRunner,
    diff_detections,
    diff_labels,
    parse_frame_detections,
    parse_frame_labels,
)

pytestmark = pytest.mark.unit


def test_parse_frame_detections() -> None:
    text = "PRED 0 car 0.9 0 0 10 10\nPRED 0 ped 0.8 20 20 30 30\nnoise\nPRED 1 car 0.7 0 0 5 5\n"
    frames = parse_frame_detections(text)
    assert set(frames) == {0, 1}
    assert len(frames[0]) == 2 and frames[0][0].label == "car"


def test_parse_frame_labels() -> None:
    assert parse_frame_labels("CLS 0 cat\nCLS 1 dog\n") == {0: "cat", 1: "dog"}


def test_diff_labels() -> None:
    diff = diff_labels({0: "cat", 1: "dog", 2: "cat"}, {0: "cat", 1: "fox", 2: "cat"})
    assert diff.frames == 3
    assert diff.agreements == 2
    assert diff.changed == 1
    assert diff.agreement_rate == pytest.approx(2 / 3)
    assert diff.disagreements[0].frame == 1


def test_diff_detections_agreement() -> None:
    incumbent = parse_frame_detections("PRED 0 car 0.9 0 0 10 10\n")
    candidate = parse_frame_detections("PRED 0 car 0.9 0 0 10 10\n")
    diff = diff_detections(incumbent, candidate, 0.5)
    assert diff.agreements == 1 and diff.changed == 0
    assert diff.added == 0 and diff.removed == 0


def test_diff_detections_label_flip() -> None:
    incumbent = parse_frame_detections("PRED 0 car 0.9 0 0 10 10\n")
    candidate = parse_frame_detections("PRED 0 truck 0.9 0 0 10 10\n")
    diff = diff_detections(incumbent, candidate, 0.5)
    assert diff.changed == 1 and diff.agreements == 0
    assert "car -> truck" in diff.disagreements[0].detail


def test_diff_detections_added_and_removed() -> None:
    incumbent = parse_frame_detections("PRED 0 car 0.9 0 0 10 10\n")
    candidate = parse_frame_detections("PRED 0 ped 0.9 50 50 60 60\n")
    diff = diff_detections(incumbent, candidate, 0.5)
    assert diff.removed == 1  # car has no candidate match
    assert diff.added == 1  # ped is new
    assert diff.agreements == 0


class _FakeRecorder:
    """ReplayRecorder double returning scripted per-command output."""

    outputs: ClassVar[dict[str, str]] = {}

    def __init__(self, board_id: str, project_root: Path) -> None:
        pass

    async def replay(
        self, name: str, replay_command: str, remote_path: str, timeout_s: float = 120.0
    ) -> tuple[int, str]:
        return 0, _FakeRecorder.outputs.get(replay_command, "")


def test_shadow_runner_end_to_end(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _FakeRecorder.outputs = {
        "old": "PRED 0 car 0.9 0 0 10 10\n",
        "new": "PRED 0 truck 0.9 0 0 10 10\n",
    }
    monkeypatch.setattr(shadow_module, "ReplayRecorder", _FakeRecorder)
    run_dir = tmp_path / "run"
    runner = ShadowRunner("agx-orin", tmp_path)
    diff = asyncio.run(runner.run("fx", "old", "new", "/tmp/s.bin", run_dir, kind="detection"))
    assert diff.changed == 1
    saved = json.loads((run_dir / "shadow-diff.json").read_text())
    assert saved["changed"] == 1
    assert (run_dir / "incumbent.txt").read_text().startswith("PRED")
