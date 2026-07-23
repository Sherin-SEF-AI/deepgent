"""Confidence-calibrated fact arbitration (#12) and pre-mortem planner (#11).

Pure logic tested directly; the pre-mortem's client and the calibrator's store
use doubles, so no server or hardware is required.
"""

import asyncio
from pathlib import Path
from typing import Any

import pytest

from deepgent.knowledge.fact_confidence import (
    FactAssertion,
    arbitrate,
    arbitrate_all,
    confidence_for,
)
from deepgent.knowledge.premortem import assemble_premortem, premortem
from deepgent.telemetry import TelemetryStore

pytestmark = pytest.mark.unit


# --- fact confidence --------------------------------------------------------


def test_confidence_by_source() -> None:
    assert confidence_for("empirical") == pytest.approx(1.0)
    assert confidence_for("datasheet_rag") == pytest.approx(0.9)
    assert confidence_for("model_memory") == pytest.approx(0.0)  # refused by constitution
    assert confidence_for("unknown_source") == pytest.approx(0.3)


def test_confidence_calibration_blend() -> None:
    # A source with observed reliability 0.5 pulls a 0.9 base halfway.
    blended = confidence_for("datasheet_rag", calibration={"datasheet_rag": 0.5})
    assert blended == pytest.approx(0.7)


def test_arbitrate_picks_highest_confidence() -> None:
    result = arbitrate(
        [
            FactAssertion("pin", "GPIO7", "model_memory"),
            FactAssertion("pin", "GPIO9", "datasheet_rag"),
            FactAssertion("pin", "GPIO9", "corpus"),
        ]
    )
    assert result.value == "GPIO9"
    assert result.source == "datasheet_rag"
    assert result.conflict is False
    assert "model_memory" in result.refused


def test_arbitrate_flags_conflict() -> None:
    result = arbitrate(
        [
            FactAssertion("voltage", "3.3", "datasheet_rag"),
            FactAssertion("voltage", "5.0", "corpus"),
        ]
    )
    assert result.value == "3.3"  # datasheet wins
    assert result.conflict is True  # corpus disagrees above threshold


def test_arbitrate_all_only_refused_is_unknown() -> None:
    report = arbitrate_all({"x": [FactAssertion("x", "v", "model_memory")]})
    assert report.facts[0].known is False
    assert report.facts[0].refused == ("model_memory",)


def test_fact_reliability_calibrator(tmp_path: Path) -> None:
    store = TelemetryStore(tmp_path / "t.db")
    try:
        for correct in (True, True, False, True, True):  # 4/5 correct
            store.record_fact_outcome("corpus", 0.7, correct)
        store.record_fact_outcome("datasheet_rag", 0.9, True)  # only 1 sample
        reliability = store.fact_reliability(min_samples=5)
        assert reliability["corpus"] == pytest.approx(0.8)
        assert "datasheet_rag" not in reliability  # below min_samples
    finally:
        store.close()


# --- pre-mortem -------------------------------------------------------------


def test_assemble_premortem_from_corpus() -> None:
    tuples = [
        {
            "symptom": "nvcc unsupported gpu arch",
            "root_cause": "sm_87 not in arch flags",
            "fix": "add -gencode arch=compute_87",
            "verification_run_id": "run-42",
        }
    ]
    pm = assemble_premortem(tuples, None)
    assert not pm.empty
    assert pm.risks[0].source == "corpus"
    assert "run-42" in pm.risks[0].provenance
    assert "apply" in pm.plan_prelude()


def test_assemble_premortem_matrix_fail() -> None:
    claim = {"status": "verified_fail", "claim": "trt10 on jp7", "evidence_run_id": "r9"}
    pm = assemble_premortem([], claim)
    assert len(pm.risks) == 1 and pm.risks[0].source == "matrix"


def test_assemble_premortem_empty() -> None:
    pm = assemble_premortem([], {"status": "verified_pass"})
    assert pm.empty
    assert pm.plan_prelude() == ""
    assert "No prior failures" in pm.render()


class _FakeRagClient:
    def __init__(self, tuples: list[dict[str, Any]], claim: dict[str, Any] | None) -> None:
        self._tuples = tuples
        self._claim = claim

    async def search_symptom(self, symptom: str, hw: str | None = None) -> list[dict[str, Any]]:
        return self._tuples

    async def query_claim(self, stack: dict[str, str]) -> dict[str, Any]:
        return self._claim or {}


def test_premortem_queries_corpus_and_matrix() -> None:
    client = _FakeRagClient(
        [{"symptom": "s", "root_cause": "c", "fix": "f", "verification_run_id": "r"}],
        {"status": "verified_fail", "claim": "bad stack", "evidence_run_id": "r2"},
    )
    pm = asyncio.run(premortem(client, "s", hw="agx", stack={"l4t": "39.0"}))  # type: ignore[arg-type]
    assert len(pm.risks) == 2  # one corpus, one matrix
