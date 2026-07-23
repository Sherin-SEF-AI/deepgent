"""Shadow-mode field-replay diffing (#9).

Replays one recorded fixture through two model versions (the incumbent and a
candidate) and produces a behavioral diff: where do they disagree on real
data, and by how much. This turns replay fixtures from pass/fail regression
tests into a validation instrument, and every disagreement is a candidate for
the failure corpus.

Prediction contract emitted by each consumer, one per line:
  detection:      PRED <frame> <label> <score> <x1> <y1> <x2> <y2>
  classification: CLS  <frame> <label>
Diff logic is pure and unit-tested; the replay itself reuses the fixture store.
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import structlog

from deepgent.evals.metrics import Box, Detection, iou
from deepgent.evals.replay import ReplayRecorder

_logger = structlog.get_logger(__name__)

_PRED = re.compile(
    r"^\s*PRED\s+(\d+)\s+(\S+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s*$"
)
_CLS = re.compile(r"^\s*CLS\s+(\d+)\s+(\S+)\s*$")


def parse_frame_detections(text: str) -> dict[int, list[Detection]]:
    """Parse PRED lines into per-frame detection lists."""
    frames: dict[int, list[Detection]] = {}
    for line in text.splitlines():
        match = _PRED.match(line)
        if not match:
            continue
        frame = int(match.group(1))
        frames.setdefault(frame, []).append(
            Detection(
                label=match.group(2),
                score=float(match.group(3)),
                box=Box(
                    float(match.group(4)),
                    float(match.group(5)),
                    float(match.group(6)),
                    float(match.group(7)),
                ),
            )
        )
    return frames


def parse_frame_labels(text: str) -> dict[int, str]:
    """Parse CLS lines into per-frame class labels."""
    frames: dict[int, str] = {}
    for line in text.splitlines():
        match = _CLS.match(line)
        if match:
            frames[int(match.group(1))] = match.group(2)
    return frames


@dataclass(frozen=True)
class FrameDisagreement:
    """One frame where incumbent and candidate diverged."""

    frame: int
    detail: str


@dataclass
class ShadowDiff:
    """Behavioral diff between two model versions over a replayed fixture."""

    kind: str
    frames: int = 0
    agreements: int = 0
    changed: int = 0
    added: int = 0
    removed: int = 0
    disagreements: list[FrameDisagreement] = field(default_factory=list)

    @property
    def agreement_rate(self) -> float:
        total = self.agreements + self.changed + self.added + self.removed
        return self.agreements / total if total else 1.0

    def to_dict(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "frames": self.frames,
            "agreements": self.agreements,
            "changed": self.changed,
            "added": self.added,
            "removed": self.removed,
            "agreement_rate": self.agreement_rate,
            "disagreements": [
                {"frame": d.frame, "detail": d.detail} for d in self.disagreements[:200]
            ],
        }

    def render(self) -> str:
        lines = [
            "# shadow-mode diff (incumbent vs candidate)",
            f"kind:            {self.kind}",
            f"frames:          {self.frames}",
            f"agreement rate:  {self.agreement_rate:.3f}",
            f"changed:         {self.changed}",
            f"added:           {self.added}",
            f"removed:         {self.removed}",
        ]
        if self.disagreements:
            lines.append("")
            lines.append("sample disagreements:")
            lines += [f"  frame {d.frame}: {d.detail}" for d in self.disagreements[:20]]
        return "\n".join(lines) + "\n"

    def persist(self, run_dir: Path) -> None:
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "shadow-diff.json").write_text(json.dumps(self.to_dict(), indent=2))
        (run_dir / "shadow-diff.txt").write_text(self.render())


def diff_labels(incumbent: dict[int, str], candidate: dict[int, str]) -> ShadowDiff:
    """Classification diff: per-frame label agreement."""
    diff = ShadowDiff(kind="classification")
    for frame in sorted(set(incumbent) | set(candidate)):
        diff.frames += 1
        a = incumbent.get(frame)
        b = candidate.get(frame)
        if a == b:
            diff.agreements += 1
        else:
            diff.changed += 1
            diff.disagreements.append(FrameDisagreement(frame, f"{a} -> {b}"))
    return diff


def diff_detections(
    incumbent: dict[int, list[Detection]],
    candidate: dict[int, list[Detection]],
    iou_thr: float = 0.5,
) -> ShadowDiff:
    """Detection diff: IoU-match boxes per frame, count agree/change/add/remove."""
    diff = ShadowDiff(kind="detection")
    for frame in sorted(set(incumbent) | set(candidate)):
        diff.frames += 1
        a = list(incumbent.get(frame, []))
        b = candidate.get(frame, [])
        matched_b: set[int] = set()
        for det_a in a:
            best_j = -1
            best_iou = iou_thr
            for j, det_b in enumerate(b):
                if j in matched_b:
                    continue
                overlap = iou(det_a.box, det_b.box)
                if overlap >= best_iou:
                    best_iou = overlap
                    best_j = j
            if best_j >= 0:
                matched_b.add(best_j)
                if b[best_j].label == det_a.label:
                    diff.agreements += 1
                else:
                    diff.changed += 1
                    diff.disagreements.append(
                        FrameDisagreement(frame, f"label {det_a.label} -> {b[best_j].label}")
                    )
            else:
                diff.removed += 1
                diff.disagreements.append(
                    FrameDisagreement(frame, f"removed {det_a.label} @ {_box(det_a.box)}")
                )
        for j, det_b in enumerate(b):
            if j not in matched_b:
                diff.added += 1
                diff.disagreements.append(
                    FrameDisagreement(frame, f"added {det_b.label} @ {_box(det_b.box)}")
                )
    return diff


def _box(box: Box) -> str:
    return f"[{box.x1:.0f},{box.y1:.0f},{box.x2:.0f},{box.y2:.0f}]"


class ShadowRunner:
    """Replays a fixture through two models and diffs their predictions."""

    def __init__(self, board_id: str, project_root: Path) -> None:
        self._recorder = ReplayRecorder(board_id, project_root)

    async def run(
        self,
        fixture: str,
        incumbent_command: str,
        candidate_command: str,
        remote_path: str,
        run_dir: Path,
        kind: str = "detection",
        iou_thr: float = 0.5,
        timeout_s: float = 120.0,
    ) -> ShadowDiff:
        _logger.info("shadow_replay", fixture=fixture, kind=kind)
        _, incumbent_out = await self._recorder.replay(
            fixture, incumbent_command, remote_path, timeout_s
        )
        _, candidate_out = await self._recorder.replay(
            fixture, candidate_command, remote_path, timeout_s
        )
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "incumbent.txt").write_text(incumbent_out)
        (run_dir / "candidate.txt").write_text(candidate_out)
        if kind == "classification":
            diff = diff_labels(parse_frame_labels(incumbent_out), parse_frame_labels(candidate_out))
        else:
            diff = diff_detections(
                parse_frame_detections(incumbent_out),
                parse_frame_detections(candidate_out),
                iou_thr,
            )
        diff.persist(run_dir)
        return diff
