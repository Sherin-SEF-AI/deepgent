"""Quantization sweep (#1), accuracy metrics/gate (#2), and power-budget model
selector (#6). Pure analysis is tested directly; on-target paths use a runner
double so live hardware is never required.
"""

import asyncio
import json
from pathlib import Path
from typing import Any, ClassVar

import pytest

import deepgent.evals.bench as bench_module
import deepgent.evals.model_selector as selector_module
import deepgent.evals.quant_sweep as sweep_module
from deepgent.boards import BoardConfig, CommandResult, add_board
from deepgent.errors import TaskExecutionError
from deepgent.evals.accuracy import (
    AccuracyGate,
    AccuracyResult,
    load_baseline,
    score_classification_files,
    score_detection_files,
)
from deepgent.evals.bench import parse_fps, parse_latency_ms, parse_named_metrics
from deepgent.evals.metrics import (
    Box,
    Detection,
    GroundTruth,
    average_precision,
    classification_accuracy,
    iou,
    mean_average_precision,
    top_k_accuracy,
)
from deepgent.evals.model_selector import (
    Candidate,
    Constraint,
    ModelSelector,
    SelectionResult,
    check_constraint,
    load_candidates,
)
from deepgent.evals.quant_sweep import (
    QuantSweepRunner,
    SweepConfig,
    SweepPoint,
    expand_grid,
    pareto_frontier,
    select_best,
)

pytestmark = pytest.mark.unit


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


# --- bench parsers ----------------------------------------------------------


def test_bench_parsers() -> None:
    out = "p99 latency 12.5 ms\n30.0 fps\nMETRIC mAP 0.812\nMETRIC top1 0.71\n"
    assert parse_latency_ms(out) == pytest.approx(12.5)
    assert parse_fps(out) == pytest.approx(30.0)
    assert parse_named_metrics(out) == {"mAP": 0.812, "top1": 0.71}


# --- detection / classification metrics ------------------------------------


def test_iou_basic() -> None:
    a = Box(0, 0, 10, 10)
    assert iou(a, a) == pytest.approx(1.0)
    assert iou(a, Box(20, 20, 30, 30)) == pytest.approx(0.0)
    # Half overlap along x: intersection 5x10=50, union 100+100-50=150.
    assert iou(a, Box(5, 0, 15, 10)) == pytest.approx(50 / 150)


def test_average_precision_perfect() -> None:
    gts = [GroundTruth("car", Box(0, 0, 10, 10)), GroundTruth("car", Box(20, 20, 30, 30))]
    preds = [
        Detection("car", 0.9, Box(0, 0, 10, 10)),
        Detection("car", 0.8, Box(20, 20, 30, 30)),
    ]
    assert average_precision(preds, gts, 0.5) == pytest.approx(1.0)


def test_average_precision_with_false_positive() -> None:
    gts = [GroundTruth("car", Box(0, 0, 10, 10))]
    preds = [
        Detection("car", 0.9, Box(0, 0, 10, 10)),  # tp
        Detection("car", 0.8, Box(50, 50, 60, 60)),  # fp
    ]
    # One TP recovers full recall at precision 1.0 -> AP 1.0; the later FP does
    # not reduce the max-envelope AP.
    assert average_precision(preds, gts, 0.5) == pytest.approx(1.0)


def test_average_precision_missed_detection() -> None:
    gts = [GroundTruth("car", Box(0, 0, 10, 10)), GroundTruth("car", Box(20, 20, 30, 30))]
    preds = [Detection("car", 0.9, Box(0, 0, 10, 10))]  # only one of two
    assert average_precision(preds, gts, 0.5) == pytest.approx(0.5)


def test_mean_average_precision_multiclass() -> None:
    gts = [GroundTruth("car", Box(0, 0, 10, 10)), GroundTruth("ped", Box(20, 20, 30, 30))]
    preds = [
        Detection("car", 0.9, Box(0, 0, 10, 10)),  # car perfect
    ]  # ped missed entirely -> AP 0
    assert mean_average_precision(preds, gts, 0.5) == pytest.approx(0.5)


def test_classification_accuracy() -> None:
    assert classification_accuracy(["a", "b", "c"], ["a", "x", "c"]) == pytest.approx(2 / 3)


def test_top_k_accuracy() -> None:
    ranked = [["a", "b"], ["x", "y"]]
    assert top_k_accuracy(ranked, ["b", "y"], k=2) == pytest.approx(1.0)
    assert top_k_accuracy(ranked, ["b", "z"], k=2) == pytest.approx(0.5)


def test_classification_accuracy_length_mismatch() -> None:
    with pytest.raises(ValueError):
        classification_accuracy(["a"], ["a", "b"])


# --- accuracy gate ----------------------------------------------------------


def test_accuracy_result_gate_logic() -> None:
    passing = AccuracyResult("mAP", measured=0.80, baseline=0.81, tolerance=0.02)
    assert passing.passed is True
    failing = AccuracyResult("mAP", measured=0.70, baseline=0.81, tolerance=0.02)
    assert failing.passed is False
    informational = AccuracyResult("mAP", measured=0.5, baseline=None, tolerance=0.0)
    assert informational.passed is True and informational.delta is None


def test_load_baseline_number_and_file(tmp_path: Path) -> None:
    assert load_baseline("0.8", "mAP") == pytest.approx(0.8)
    f = tmp_path / "b.json"
    f.write_text(json.dumps({"mAP": 0.77}))
    assert load_baseline(str(f), "mAP") == pytest.approx(0.77)
    with pytest.raises(TaskExecutionError):
        load_baseline(str(f), "top1")


def test_score_files(tmp_path: Path) -> None:
    preds = tmp_path / "p.json"
    gts = tmp_path / "g.json"
    preds.write_text(json.dumps([{"label": "car", "score": 0.9, "box": [0, 0, 10, 10]}]))
    gts.write_text(json.dumps([{"label": "car", "box": [0, 0, 10, 10]}]))
    assert score_detection_files(preds, gts, 0.5) == pytest.approx(1.0)
    cls_p = tmp_path / "cp.json"
    cls_t = tmp_path / "ct.json"
    cls_p.write_text(json.dumps(["a", "b"]))
    cls_t.write_text(json.dumps(["a", "c"]))
    assert score_classification_files(cls_p, cls_t) == pytest.approx(0.5)


# --- quant sweep: Pareto ----------------------------------------------------


def test_expand_grid() -> None:
    grid = expand_grid(["fp16", "int8"], [1, 2], ["gpu"])
    assert len(grid) == 4
    assert SweepConfig("int8", 2, "gpu") in grid


def _point(label_parts: tuple[str, int, str], lat: float, en: float, acc: float) -> SweepPoint:
    return SweepPoint(
        config=SweepConfig(*label_parts),
        ok=True,
        latency_ms=lat,
        fps=1000.0 / lat,
        energy_j=en,
        power_w=en,
        accuracy=acc,
    )


def test_pareto_frontier_excludes_dominated() -> None:
    fast = _point(("int8", 1, "gpu"), lat=5.0, en=2.0, acc=0.80)
    accurate = _point(("fp16", 1, "gpu"), lat=9.0, en=4.0, acc=0.85)
    dominated = _point(("fp16", 2, "gpu"), lat=10.0, en=5.0, acc=0.80)  # worse than both
    frontier = pareto_frontier([fast, accurate, dominated])
    labels = {p.config.label for p in frontier}
    assert labels == {"int8-b1-gpu", "fp16-b1-gpu"}


def test_select_best_respects_constraints() -> None:
    fast = _point(("int8", 1, "gpu"), lat=5.0, en=20.0, acc=0.80)
    frugal = _point(("int8", 2, "gpu"), lat=8.0, en=6.0, acc=0.82)
    frontier = pareto_frontier([fast, frugal])
    assert select_best(frontier).config.label == "int8-b1-gpu"  # min latency
    # Cap power at 10W -> only the frugal config qualifies.
    assert select_best(frontier, max_power_w=10.0).config.label == "int8-b2-gpu"
    assert select_best(frontier, min_fps=1000.0) is None


# --- model selector constraint ---------------------------------------------


def test_check_constraint() -> None:
    c = Constraint(max_power_w=15.0, min_fps=30.0)
    assert check_constraint(True, 20.0, 40.0, 12.0, None, c) == ()
    violations = check_constraint(True, 20.0, 20.0, 18.0, None, c)
    assert any("power" in v for v in violations)
    assert any("fps" in v for v in violations)


def test_load_candidates(tmp_path: Path) -> None:
    f = tmp_path / "m.json"
    f.write_text(json.dumps([{"name": "yolo-n", "command": "./bench yolo-n"}]))
    cands = load_candidates(f)
    assert cands == [Candidate("yolo-n", "./bench yolo-n")]
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps([{"name": "x"}]))
    with pytest.raises(TaskExecutionError):
        load_candidates(bad)


# --- on-target paths with a runner double ----------------------------------


class _FakeBenchRunner:
    """Maps a substring of the command to a scripted stdout."""

    outputs: ClassVar[dict[str, str]] = {}

    def __init__(self, board: BoardConfig) -> None:
        pass

    async def __aenter__(self) -> "_FakeBenchRunner":
        return self

    async def __aexit__(self, *args: Any) -> None:
        return None

    async def run(self, command: str, timeout_s: float = 60.0) -> CommandResult:
        for key, out in _FakeBenchRunner.outputs.items():
            if key in command:
                return CommandResult(command, 0, out, "", False)
        return CommandResult(command, 0, "", "", False)

    async def capture_metrics(self, duration_s: float, interval_ms: int = 500) -> dict[str, float]:
        return {"power_mean_w": 12.0, "energy_j": 24.0}


def test_quant_sweep_end_to_end(
    fake_board: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _FakeBenchRunner.outputs = {
        "int8": "latency 5.0 ms\n200 fps\nMETRIC mAP 0.80\n",
        "fp16": "latency 9.0 ms\n110 fps\nMETRIC mAP 0.85\n",
    }
    monkeypatch.setattr(sweep_module, "open_runner", lambda b: _FakeBenchRunner(b))
    runner = QuantSweepRunner("agx-orin", tmp_path / "run")
    configs = expand_grid(["fp16", "int8"], [1], ["gpu"])
    result = asyncio.run(runner.run("bench {precision} {batch} {device}", configs, 1.0, "mAP"))
    assert len(result.points) == 2
    assert len(result.frontier) == 2  # int8 faster, fp16 more accurate
    assert (tmp_path / "run" / "quant-sweep.json").is_file()


def test_accuracy_gate_end_to_end(fake_board: None, monkeypatch: pytest.MonkeyPatch) -> None:
    _FakeBenchRunner.outputs = {"eval": "METRIC mAP 0.83\n"}
    monkeypatch.setattr(bench_module, "open_runner", lambda b: _FakeBenchRunner(b))
    result = asyncio.run(AccuracyGate().run("agx-orin", "eval", "mAP", 0.80, 0.01, 1.0))
    assert result.measured == pytest.approx(0.83)
    assert result.passed is True


def test_accuracy_gate_missing_metric_raises(
    fake_board: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    _FakeBenchRunner.outputs = {"eval": "no metric here\n"}
    monkeypatch.setattr(bench_module, "open_runner", lambda b: _FakeBenchRunner(b))
    with pytest.raises(TaskExecutionError):
        asyncio.run(AccuracyGate().run("agx-orin", "eval", "mAP", 0.8, 0.0, 1.0))


def test_model_selector_end_to_end(
    fake_board: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _FakeBenchRunner.outputs = {
        "big": "latency 40 ms\n20 fps\n",
        "small": "latency 20 ms\n50 fps\n",
    }
    monkeypatch.setattr(selector_module, "open_runner", lambda b: _FakeBenchRunner(b))
    selector = ModelSelector("agx-orin", tmp_path / "run")
    candidates = [Candidate("big", "bench big"), Candidate("small", "bench small")]
    result = asyncio.run(selector.run(candidates, Constraint(min_fps=30.0), 1.0))
    assert isinstance(result, SelectionResult)
    assert result.winner is not None and result.winner.name == "small"
    assert (tmp_path / "run" / "model-selection.json").is_file()


# --- WO-42 verification metrics: quant-sweep knee ---------------------------


def test_quant_sweep_knee_picks_best_fps_per_watt() -> None:
    from deepgent.evals.quant_sweep import knee

    fast_hot = _point(("int8", 1, "gpu"), lat=5.0, en=20.0, acc=0.80)  # 200 fps / 20W = 10
    frugal = _point(("int8", 2, "gpu"), lat=8.0, en=6.0, acc=0.82)  # 125 fps / 6W ~= 20.8
    frontier = pareto_frontier([fast_hot, frugal])
    assert knee(frontier).config.label == "int8-b2-gpu"
    assert knee([]) is None
