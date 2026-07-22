"""Tier 3 leverage: driver scaffolder, skill self-authoring, PR review."""

from pathlib import Path

import pytest

from deepgent.evals.pr_review import build_review
from deepgent.evals.runner import GoldenRunResult
from deepgent.evals.schema import GoldenTask, score
from deepgent.generators import scaffold_driver, spec_from_chunks
from deepgent.generators.driver_scaffold import DriverSpec, RegisterFact
from deepgent.knowledge.skill_author import cluster_tuples, draft_skill_candidates


class TestDriverScaffolder:
    @pytest.mark.unit
    def test_sourced_facts_appear_with_provenance(self, tmp_path: Path) -> None:
        spec = DriverSpec(
            device_name="IMX219 Camera",
            compatible="sony,imx219",
            i2c_address="0x10",
            kind="i2c",
            registers=(
                RegisterFact(
                    name="CHIP_ID",
                    address="0x0000",
                    description="chip id",
                    provenance="imx219-ds/registers",
                ),
            ),
        )
        output = scaffold_driver(spec)
        driver = output.files["drivers/imx219_camera.c"]
        assert "IMX219_CAMERA_I2C_ADDR 0x10" in driver
        assert "0x0000" in driver
        assert "imx219-ds/registers" in driver
        assert "sony,imx219" in output.files["dts/imx219_camera.dtsi"]
        written = output.write(tmp_path)
        assert any(p.name == "imx219_camera.c" for p in written)

    @pytest.mark.unit
    def test_unsourced_values_are_todo_not_guessed(self) -> None:
        spec = DriverSpec(
            device_name="Unknown Sensor",
            compatible="vendor,unknown",
            i2c_address=None,
            kind="i2c",
        )
        output = scaffold_driver(spec)
        driver = output.files["drivers/unknown_sensor.c"]
        assert "TODO" in driver
        assert "no register map sourced from datasheet-rag" in output.todos
        assert "I2C address not sourced from any datasheet chunk" in output.todos

    @pytest.mark.unit
    def test_spec_from_chunks_extracts_only_sourced(self) -> None:
        chunks = [
            {
                "doc": "imx219.pdf",
                "section": "I2C",
                "text": "The device I2C address is 0x10 by default.",
            },
            {
                "doc": "imx219.pdf",
                "section": "Registers",
                "text": "MODEL_ID 0x0000 holds the model. FRAME_LENGTH 0x0160 sets frames.",
            },
        ]
        spec = spec_from_chunks("IMX219", "sony,imx219", "i2c", chunks)
        assert spec.i2c_address == "0x10"
        names = {r.name for r in spec.registers}
        assert "MODEL_ID" in names
        assert spec.unresolved == ()

    @pytest.mark.unit
    def test_spec_from_empty_chunks_is_all_unresolved(self) -> None:
        spec = spec_from_chunks("X", "v,x", "i2c", [])
        assert spec.i2c_address is None
        assert len(spec.unresolved) == 2


def _tuples(n: int, symptom: str) -> list[dict[str, str]]:
    return [
        {
            "symptom": f"{symptom} variant {i}",
            "root_cause": "cause",
            "fix": "fix",
            "verification_run_id": f"gt-{i}",
        }
        for i in range(n)
    ]


class TestSkillAuthoring:
    @pytest.mark.unit
    def test_cluster_needs_minimum(self) -> None:
        assert cluster_tuples(_tuples(2, "tegrastats hang")) == []
        candidates = cluster_tuples(_tuples(3, "tegrastats hang"))
        assert len(candidates) == 1
        assert candidates[0].theme == "tegrastats"

    @pytest.mark.unit
    def test_drafts_are_suffixed_and_cite_evidence(self, tmp_path: Path) -> None:
        written = draft_skill_candidates(_tuples(3, "nvcc arch mismatch"), tmp_path)
        assert len(written) == 1
        assert written[0].parent.name.endswith("-draft")
        body = written[0].read_text()
        assert "Human review required" in body
        assert "verified by: gt-0" in body

    @pytest.mark.unit
    def test_mixed_themes_only_large_clusters(self) -> None:
        tuples = _tuples(3, "thermal throttle") + _tuples(1, "ssh refused")
        candidates = cluster_tuples(tuples)
        assert {c.theme for c in candidates} == {"thermal"}


def _result(task_id: str, passed: bool, metrics: dict[str, float]) -> GoldenRunResult:
    task = GoldenTask.model_validate(
        {
            "id": task_id,
            "title": "t",
            "class": "perception/quantization",
            "board": "agx-orin",
            "success": [{"metric": "map_delta", "op": ">=", "value": -1.0}],
            "budget_usd": 1,
            "timeout_min": 1,
        }
    )
    all_metrics = {"map_delta": 0.0 if passed else -2.0, **metrics}
    criteria = score(all_metrics, task.success)
    return GoldenRunResult(task=task, run_dir=Path("/tmp"), metrics=all_metrics, criteria=criteria)


class TestHardwareReview:
    @pytest.mark.unit
    def test_passing_review_carries_measurements(self, tmp_path: Path) -> None:
        (tmp_path / "golden").mkdir()
        result = _result("gt-0007", True, {"p99_latency_ms": 22.0, "power_mean_w": 25.0})
        review = build_review([result], tmp_path)
        assert not review.has_regressions
        body = review.render_markdown()
        assert "measurements pass" in body
        assert "p99_latency_ms=22.00" in body
        assert "power_mean_w=25.00" in body

    @pytest.mark.unit
    def test_failing_golden_requests_changes(self, tmp_path: Path) -> None:
        (tmp_path / "golden").mkdir()
        result = _result("gt-0007", False, {"p99_latency_ms": 40.0})
        review = build_review([result], tmp_path)
        assert review.has_regressions
        assert "changes requested" in review.render_markdown()

    @pytest.mark.unit
    def test_missing_baseline_is_not_a_regression(self, tmp_path: Path) -> None:
        (tmp_path / "golden").mkdir()
        result = _result("gt-new", True, {"wall_s": 10.0})
        review = build_review([result], tmp_path)
        assert not review.has_regressions
