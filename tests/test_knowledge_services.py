"""Matrix/corpus services, release watch, and the evals regression gate."""

import json
from pathlib import Path
from typing import Any

import pytest
from deepgent_server import create_app
from deepgent_server.knowledge import stack_matches
from fastapi.testclient import TestClient

from deepgent.errors import KnowledgeError
from deepgent.evals.runner import (
    GoldenRunResult,
    diff_against_baseline,
    update_baseline,
)
from deepgent.evals.schema import GoldenTask
from deepgent.knowledge.release_watch import newer_l4t_tags, tag_key

TOKEN = "test-token-1234"


@pytest.fixture
def api(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("DEEPGENT_SERVER_KNOWLEDGE_DB", str(tmp_path / "k.db"))
    app = create_app(db_path=tmp_path / "rag.db", token=TOKEN)
    return TestClient(app, headers={"Authorization": f"Bearer {TOKEN}"})


class TestMatrix:
    @pytest.mark.unit
    def test_unknown_is_a_first_class_answer(self, api: TestClient) -> None:
        result = api.post("/matrix/query", json={"stack": {"l4t": "36.4.3"}})
        assert result.json() == {"status": "unknown"}

    @pytest.mark.unit
    def test_claim_round_trip_with_evidence(self, api: TestClient) -> None:
        added = api.post(
            "/matrix/claims",
            json={
                "stack": {"l4t": "36.4.3", "trt": "10.3"},
                "claim": "INT8 engine build works on jp6",
                "status": "verified_pass",
                "evidence_run_id": "gt-0001-20260722T120000Z",
            },
        )
        assert added.status_code == 200

        hit = api.post(
            "/matrix/query",
            json={"stack": {"l4t": "36.4.3", "trt": "10.3", "ros": "humble"}},
        ).json()
        assert hit["status"] == "verified_pass"
        assert hit["evidence_run_id"] == "gt-0001-20260722T120000Z"

        miss = api.post("/matrix/query", json={"stack": {"l4t": "36.4.3", "trt": "10.16.2"}}).json()
        assert miss == {"status": "unknown"}

    @pytest.mark.unit
    def test_status_is_constrained(self, api: TestClient) -> None:
        bad = api.post(
            "/matrix/claims",
            json={
                "stack": {"l4t": "36.4.3"},
                "claim": "x",
                "status": "model_says_so",
                "evidence_run_id": "r",
            },
        )
        assert bad.status_code == 422

    @pytest.mark.unit
    def test_stack_matching_semantics(self) -> None:
        claim = {"l4t": "36.4.3", "trt": "10.3"}
        assert stack_matches(claim, {"l4t": "36.4.3", "trt": "10.3", "extra": "z"})
        assert not stack_matches(claim, {"l4t": "36.4.3"})
        assert not stack_matches(claim, {"l4t": "36.4.3", "trt": "8.6"})


class TestCorpus:
    @pytest.mark.unit
    def test_tuple_round_trip(self, api: TestClient) -> None:
        api.post(
            "/corpus/tuples",
            json={
                "symptom": "nvcc fatal: unsupported gpu architecture sm_87",
                "hw_config": "agx-orin",
                "versions": {"l4t": "36.4.3"},
                "root_cause": "CUDA 11 toolchain used instead of the jp6 container",
                "fix": "build inside deepgent/jp6 image",
                "verification_run_id": "gt-0001-x",
            },
        )
        hits = api.post(
            "/corpus/search",
            json={"text": "nvcc unsupported architecture", "hw": "agx-orin"},
        ).json()["tuples"]
        assert len(hits) == 1
        assert hits[0]["fix"].startswith("build inside")

        other_hw = api.post(
            "/corpus/search", json={"text": "nvcc unsupported", "hw": "pi5-hailo"}
        ).json()["tuples"]
        assert other_hw == []


class TestReleaseWatch:
    @pytest.mark.unit
    def test_tag_ordering(self) -> None:
        assert tag_key("r36.4.0") == (36, 4, 0)
        assert tag_key("r36.4") == (36, 4, 0)
        assert tag_key("latest") is None
        newer = newer_l4t_tags("r36.4.0", ["r36.2.0", "r36.4.0", "r36.4.3", "r38.1", "junk"])
        assert newer == ["r36.4.3", "r38.1"]

    @pytest.mark.unit
    def test_bad_pin_is_actionable(self) -> None:
        with pytest.raises(KnowledgeError, match=r"not an rX\.Y"):
            newer_l4t_tags("not-a-tag", ["r36.4.0"])


def _result(task_id: str, passed: bool, metrics: dict[str, float]) -> GoldenRunResult:
    task = GoldenTask.model_validate(
        {
            "id": task_id,
            "title": "t",
            "class": "bringup/cuda-smoke",
            "board": "agx-orin",
            "success": [{"metric": "kernel_ok", "op": "==", "value": 1}],
            "budget_usd": 1,
            "timeout_min": 1,
        }
    )
    criteria_metrics = {"kernel_ok": 1.0 if passed else 0.0, **metrics}
    from deepgent.evals.schema import score

    criteria = score(criteria_metrics, task.success)
    return GoldenRunResult(
        task=task, run_dir=Path("/tmp"), metrics=criteria_metrics, criteria=criteria
    )


class TestRegressionGate:
    @pytest.mark.unit
    def test_missing_baseline_flagged(self, tmp_path: Path) -> None:
        (tmp_path / "golden").mkdir()
        findings = diff_against_baseline(_result("gt-x", True, {}), tmp_path)
        assert "no baseline" in findings[0]

    @pytest.mark.unit
    def test_pass_to_fail_is_regression(self, tmp_path: Path) -> None:
        (tmp_path / "golden").mkdir()
        update_baseline(_result("gt-x", True, {"wall_s": 10.0}), tmp_path)
        findings = diff_against_baseline(_result("gt-x", False, {"wall_s": 10.0}), tmp_path)
        assert any("previously passed and now fails" in f for f in findings)

    @pytest.mark.unit
    def test_cost_degradation_over_15_percent_flagged(self, tmp_path: Path) -> None:
        (tmp_path / "golden").mkdir()
        update_baseline(_result("gt-x", True, {"wall_s": 10.0}), tmp_path)
        findings = diff_against_baseline(_result("gt-x", True, {"wall_s": 12.0}), tmp_path)
        assert any("wall_s degraded 20%" in f for f in findings)

    @pytest.mark.unit
    def test_within_budget_is_clean(self, tmp_path: Path) -> None:
        (tmp_path / "golden").mkdir()
        update_baseline(_result("gt-x", True, {"wall_s": 10.0}), tmp_path)
        assert diff_against_baseline(_result("gt-x", True, {"wall_s": 11.0}), tmp_path) == []

    @pytest.mark.unit
    def test_baseline_file_is_json(self, tmp_path: Path) -> None:
        (tmp_path / "golden").mkdir()
        update_baseline(_result("gt-x", True, {"wall_s": 10.0}), tmp_path)
        data = json.loads((tmp_path / "golden" / "baselines.json").read_text())
        assert data["gt-x"]["passed"] is True


class TestClientKnowledgeMethods:
    @pytest.mark.unit
    def test_query_claim_and_search_symptom(self, api: TestClient, tmp_path: Path) -> None:
        import asyncio

        import httpx

        from deepgent.knowledge import RagClient, build_knowledge_tools

        client = RagClient("http://testserver", TOKEN, transport=httpx.ASGITransport(app=api.app))
        tools = {t.name: t for t in build_knowledge_tools(client)}
        assert set(tools) == {"search", "get_chunk", "query_claim", "search_symptom"}

        unknown = asyncio.run(tools["query_claim"].handler({"stack": {"l4t": "39.2"}}))
        payload: dict[str, Any] = json.loads(unknown["content"][0]["text"])
        assert payload == {"status": "unknown"}

        empty = asyncio.run(tools["search_symptom"].handler({"text": "novel failure"}))
        symptom_payload = json.loads(empty["content"][0]["text"])
        assert symptom_payload["unknown"] is True
        asyncio.run(client.aclose())
