"""Closed-loop accuracy validation and regression gate (#2).

Runs an on-device evaluation, obtains an accuracy metric (either parsed from a
'METRIC <name> <value>' line the device prints, or computed here from
device-produced predictions plus local ground truth), compares it to a pinned
baseline, and gates on regression beyond a tolerance. This operationalizes the
mAP-delta half of the definition of done that raw fps numbers ignore.
"""

import json
from dataclasses import dataclass
from pathlib import Path

import structlog

from deepgent.errors import TaskExecutionError
from deepgent.evals.bench import run_benchmark
from deepgent.evals.metrics import (
    Box,
    Detection,
    GroundTruth,
    classification_accuracy,
    mean_average_precision,
)

_logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class AccuracyResult:
    """Measured accuracy versus a baseline, with the gate verdict."""

    metric: str
    measured: float
    baseline: float | None
    tolerance: float

    @property
    def delta(self) -> float | None:
        return None if self.baseline is None else self.measured - self.baseline

    @property
    def passed(self) -> bool:
        """No baseline means informational only (passes); else delta >= -tol."""
        if self.baseline is None:
            return True
        return self.measured - self.baseline >= -self.tolerance

    def to_dict(self) -> dict[str, object]:
        return {
            "metric": self.metric,
            "measured": self.measured,
            "baseline": self.baseline,
            "delta": self.delta,
            "tolerance": self.tolerance,
            "passed": self.passed,
        }

    def render(self) -> str:
        lines = [
            "# accuracy gate",
            f"metric:   {self.metric}",
            f"measured: {self.measured:.4f}",
        ]
        if self.baseline is not None:
            assert self.delta is not None
            lines.append(f"baseline: {self.baseline:.4f}")
            lines.append(f"delta:    {self.delta:+.4f}  (tolerance {self.tolerance:.4f})")
        lines.append(f"result:   {'PASS' if self.passed else 'FAIL'}")
        return "\n".join(lines) + "\n"


def load_detections(data: str) -> list[Detection]:
    """Parse a predictions JSON array into Detection objects."""
    parsed = json.loads(data)
    detections: list[Detection] = []
    for item in parsed:
        box = item["box"]
        detections.append(
            Detection(
                label=str(item["label"]),
                score=float(item.get("score", 1.0)),
                box=Box(float(box[0]), float(box[1]), float(box[2]), float(box[3])),
            )
        )
    return detections


def load_ground_truths(data: str) -> list[GroundTruth]:
    """Parse a ground-truth JSON array into GroundTruth objects."""
    parsed = json.loads(data)
    truths: list[GroundTruth] = []
    for item in parsed:
        box = item["box"]
        truths.append(
            GroundTruth(
                label=str(item["label"]),
                box=Box(float(box[0]), float(box[1]), float(box[2]), float(box[3])),
            )
        )
    return truths


def score_detection_files(pred_path: Path, gt_path: Path, iou_thr: float = 0.5) -> float:
    """mAP@iou from a local predictions file and ground-truth file."""
    preds = load_detections(pred_path.read_text())
    gts = load_ground_truths(gt_path.read_text())
    return mean_average_precision(preds, gts, iou_thr)


def score_classification_files(pred_path: Path, truth_path: Path) -> float:
    """Top-1 accuracy from a local predictions file and labels file."""
    predicted = [str(x) for x in json.loads(pred_path.read_text())]
    truth = [str(x) for x in json.loads(truth_path.read_text())]
    return classification_accuracy(predicted, truth)


def load_baseline(baseline: str | None, metric: str) -> float | None:
    """Resolve a baseline: a bare number, or a JSON file keyed by metric name."""
    if baseline is None:
        return None
    try:
        return float(baseline)
    except ValueError:
        pass
    path = Path(baseline)
    if not path.is_file():
        raise TaskExecutionError(f"baseline '{baseline}' is neither a number nor a file")
    table = json.loads(path.read_text())
    if metric not in table:
        raise TaskExecutionError(f"baseline file {path} has no entry for metric '{metric}'")
    return float(table[metric])


class AccuracyGate:
    """Runs an on-device eval and gates the metric against a baseline."""

    async def run(
        self,
        board: str,
        command: str,
        metric: str,
        baseline: float | None,
        tolerance: float = 0.0,
        capture_s: float = 120.0,
    ) -> AccuracyResult:
        """Run the eval command; the device must print 'METRIC <metric> <v>'."""
        result = await run_benchmark(board, command, capture_s)
        if not result.ok:
            raise TaskExecutionError(f"accuracy eval exited {result.exit_status} on '{board}'")
        if metric not in result.named:
            raise TaskExecutionError(
                f"eval output carried no 'METRIC {metric} <value>' line; "
                f"found metrics: {sorted(result.named) or 'none'}"
            )
        measured = result.named[metric]
        _logger.info("accuracy_measured", metric=metric, measured=measured, baseline=baseline)
        return AccuracyResult(
            metric=metric, measured=measured, baseline=baseline, tolerance=tolerance
        )
