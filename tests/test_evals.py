"""Golden schema, scorer, run directories, and the gt-0001 hardware golden."""

import asyncio
import json
from pathlib import Path

import pytest

from deepgent.boards import load_registry
from deepgent.errors import GoldenError
from deepgent.evals import (
    GoldenTask,
    SuccessCriterion,
    create_run_dir,
    find_golden_file,
    load_golden,
    run_golden,
    score,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestGoldenSchema:
    @pytest.mark.unit
    def test_gt_0001_yaml_is_valid(self) -> None:
        task = load_golden(REPO_ROOT / "golden" / "gt-0001.yaml")
        assert task.id == "gt-0001"
        assert task.task_class == "bringup/cuda-smoke"
        assert task.board == "agx-orin"
        metrics = {c.metric for c in task.success}
        assert metrics >= {"run_exit_code", "kernel_ok", "tegrastats_samples"}
        assert task.timeout_min > 0

    @pytest.mark.unit
    def test_missing_file_is_actionable(self, tmp_path: Path) -> None:
        with pytest.raises(GoldenError, match="does not exist"):
            load_golden(tmp_path / "gt-9999.yaml")

    @pytest.mark.unit
    def test_invalid_schema_rejected(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad.yaml"
        bad.write_text("id: x\ntitle: y\n")
        with pytest.raises(GoldenError, match="invalid golden task"):
            load_golden(bad)

    @pytest.mark.unit
    def test_invalid_op_rejected(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad-op.yaml"
        bad.write_text(
            "id: x\ntitle: y\nclass: c\nboard: b\n"
            "success:\n  - {metric: m, op: '~=', value: 1}\n"
            "budget_usd: 1\ntimeout_min: 1\n"
        )
        with pytest.raises(GoldenError, match="invalid golden task"):
            load_golden(bad)


class TestScorer:
    @pytest.mark.unit
    @pytest.mark.parametrize(
        ("op", "actual", "expected", "passed"),
        [
            (">=", 5.0, 5.0, True),
            (">=", 4.9, 5.0, False),
            ("<=", 25.0, 25.0, True),
            ("<=", 25.1, 25.0, False),
            ("==", 0.0, 0.0, True),
            ("==", 1.0, 0.0, False),
            ("!=", 1.0, 0.0, True),
            ("!=", 0.0, 0.0, False),
            (">", 5.1, 5.0, True),
            (">", 5.0, 5.0, False),
            ("<", 4.9, 5.0, True),
            ("<", 5.0, 5.0, False),
        ],
    )
    def test_every_op(self, op: str, actual: float, expected: float, passed: bool) -> None:
        criteria = [SuccessCriterion(metric="m", op=op, value=expected)]  # type: ignore[arg-type]
        results = score({"m": actual}, criteria)
        assert results[0].passed is passed

    @pytest.mark.unit
    def test_missing_metric_fails_explicitly(self) -> None:
        results = score({}, [SuccessCriterion(metric="fps", op=">=", value=30)])
        assert not results[0].passed
        assert results[0].actual is None
        assert "missing" in results[0].describe()


class TestRunDirs:
    @pytest.mark.unit
    def test_create_run_dir(self, tmp_path: Path) -> None:
        run_dir = create_run_dir("gt-0001", tmp_path)
        assert run_dir.is_dir()
        assert run_dir.parent == tmp_path / ".deepgent" / "runs"
        assert run_dir.name.startswith("gt-0001-")

    @pytest.mark.unit
    def test_find_golden_file(self) -> None:
        assert find_golden_file("gt-0001", REPO_ROOT).is_file()


class TestRunGolden:
    @pytest.mark.unit
    def test_unknown_class_is_actionable(self, tmp_path: Path) -> None:
        golden_dir = tmp_path / "golden"
        golden_dir.mkdir()
        (golden_dir / "gt-x.yaml").write_text(
            "id: gt-x\ntitle: t\nclass: nonexistent/class\nboard: b\n"
            "success:\n  - {metric: m, op: '==', value: 0}\n"
            "budget_usd: 1\ntimeout_min: 1\n"
        )
        with pytest.raises(GoldenError, match="no implementation"):
            asyncio.run(run_golden("gt-x", tmp_path))

    @pytest.mark.unit
    def test_result_artifacts_written(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import deepgent.evals.runner as runner_module

        golden_dir = tmp_path / "golden"
        golden_dir.mkdir()
        (golden_dir / "gt-fake.yaml").write_text(
            "id: gt-fake\ntitle: t\nclass: bringup/cuda-smoke\nboard: b\n"
            "success:\n  - {metric: kernel_ok, op: '==', value: 1}\n"
            "budget_usd: 1\ntimeout_min: 1\n"
        )

        async def fake_impl(task: GoldenTask, run_dir: Path) -> dict[str, float]:
            return {"kernel_ok": 1.0}

        monkeypatch.setitem(runner_module.IMPLEMENTATIONS, "bringup/cuda-smoke", fake_impl)
        result = asyncio.run(run_golden("gt-fake", tmp_path))
        assert result.passed
        metrics = json.loads((result.run_dir / "metrics.json").read_text())
        assert metrics == {"kernel_ok": 1.0}
        outcome = json.loads((result.run_dir / "result.json").read_text())
        assert outcome["passed"] is True


requires_board = pytest.mark.skipif(
    "agx-orin" not in load_registry(),
    reason="board 'agx-orin' is not registered in ~/.deepgent/boards.toml",
)


@pytest.mark.hardware
@requires_board
def test_gt_0001_end_to_end_on_board() -> None:
    """The Phase 0 exit golden, run for real against the registered board."""
    result = asyncio.run(run_golden("gt-0001", REPO_ROOT))
    assert result.passed, [c.describe() for c in result.criteria]
