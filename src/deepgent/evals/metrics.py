"""Deterministic accuracy metrics for the closed-loop accuracy gate (#2).

Real detection mAP (VOC all-points AP over IoU-matched boxes) and
classification top-1/top-5, computed from predictions plus ground truth. Pure
functions, no hardware, so the gate's scoring is unit-tested exactly.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Box:
    """Axis-aligned box in x1, y1, x2, y2 pixel coordinates."""

    x1: float
    y1: float
    x2: float
    y2: float

    @property
    def area(self) -> float:
        return max(0.0, self.x2 - self.x1) * max(0.0, self.y2 - self.y1)


@dataclass(frozen=True)
class Detection:
    """One predicted box with a class label and confidence score."""

    label: str
    score: float
    box: Box


@dataclass(frozen=True)
class GroundTruth:
    """One ground-truth box with a class label."""

    label: str
    box: Box


def iou(a: Box, b: Box) -> float:
    """Intersection-over-union of two boxes."""
    ix1 = max(a.x1, b.x1)
    iy1 = max(a.y1, b.y1)
    ix2 = min(a.x2, b.x2)
    iy2 = min(a.y2, b.y2)
    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    union = a.area + b.area - inter
    return inter / union if union > 0 else 0.0


def average_precision(
    predictions: list[Detection], ground_truths: list[GroundTruth], iou_thr: float = 0.5
) -> float:
    """VOC all-points AP for a single class.

    Predictions are ranked by score; each greedily matches the highest-IoU
    unmatched ground truth above the threshold. Precision/recall are
    accumulated and integrated as the area under the (monotone-decreasing
    envelope of the) PR curve.
    """
    n_gt = len(ground_truths)
    if n_gt == 0:
        return 0.0
    ordered = sorted(predictions, key=lambda d: d.score, reverse=True)
    matched = [False] * n_gt
    tp = [0.0] * len(ordered)
    fp = [0.0] * len(ordered)
    for i, pred in enumerate(ordered):
        best_iou = 0.0
        best_j = -1
        for j, gt in enumerate(ground_truths):
            if matched[j]:
                continue
            overlap = iou(pred.box, gt.box)
            if overlap > best_iou:
                best_iou = overlap
                best_j = j
        if best_j >= 0 and best_iou >= iou_thr:
            matched[best_j] = True
            tp[i] = 1.0
        else:
            fp[i] = 1.0

    cum_tp = 0.0
    cum_fp = 0.0
    recalls = [0.0]
    precisions = [1.0]
    for i in range(len(ordered)):
        cum_tp += tp[i]
        cum_fp += fp[i]
        recalls.append(cum_tp / n_gt)
        precisions.append(cum_tp / (cum_tp + cum_fp))

    # Monotone-decreasing precision envelope, then integrate over recall.
    for i in range(len(precisions) - 2, -1, -1):
        precisions[i] = max(precisions[i], precisions[i + 1])
    ap = 0.0
    for i in range(1, len(recalls)):
        ap += (recalls[i] - recalls[i - 1]) * precisions[i]
    return ap


def mean_average_precision(
    predictions: list[Detection], ground_truths: list[GroundTruth], iou_thr: float = 0.5
) -> float:
    """mAP across all classes present in the ground truth."""
    classes = sorted({gt.label for gt in ground_truths})
    if not classes:
        return 0.0
    total = 0.0
    for label in classes:
        preds = [p for p in predictions if p.label == label]
        gts = [g for g in ground_truths if g.label == label]
        total += average_precision(preds, gts, iou_thr)
    return total / len(classes)


def classification_accuracy(predicted: list[str], truth: list[str]) -> float:
    """Top-1 accuracy over paired predicted/true labels."""
    if not truth:
        return 0.0
    if len(predicted) != len(truth):
        raise ValueError(f"length mismatch: {len(predicted)} predictions vs {len(truth)} labels")
    correct = sum(1 for p, t in zip(predicted, truth, strict=True) if p == t)
    return correct / len(truth)


def top_k_accuracy(ranked: list[list[str]], truth: list[str], k: int = 5) -> float:
    """Top-k accuracy: truth appears in the first k ranked predictions."""
    if not truth:
        return 0.0
    if len(ranked) != len(truth):
        raise ValueError(f"length mismatch: {len(ranked)} predictions vs {len(truth)} labels")
    correct = sum(1 for preds, t in zip(ranked, truth, strict=True) if t in preds[:k])
    return correct / len(truth)
