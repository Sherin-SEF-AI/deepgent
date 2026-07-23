"""Empirical skill lifecycle (#13) and reflexion critic (#15).

Pure logic tested directly; the corpus-backed reflexion path uses a client
double, so no server is required.
"""

import asyncio
import json
from typing import Any

import pytest

from deepgent.core.reflexion import reflect, reflect_with_corpus
from deepgent.knowledge.skill_lifecycle import (
    AblationRecord,
    analyze_lifecycle,
    evaluate_skills,
    load_ablation,
)

pytestmark = pytest.mark.unit


# --- skill lifecycle --------------------------------------------------------


def _records(
    skill: str,
    with_pass: int,
    with_fail: int,
    without_pass: int,
    without_fail: int,
    with_loops: int = 3,
    without_loops: int = 3,
) -> list[AblationRecord]:
    rows: list[AblationRecord] = []
    rows += [AblationRecord(skill, True, True, with_loops) for _ in range(with_pass)]
    rows += [AblationRecord(skill, True, False, with_loops) for _ in range(with_fail)]
    rows += [AblationRecord(skill, False, True, without_loops) for _ in range(without_pass)]
    rows += [AblationRecord(skill, False, False, without_loops) for _ in range(without_fail)]
    return rows


def test_promote_high_lift_skill() -> None:
    # with-skill 100% pass, without-skill 25% pass -> lift 0.75.
    records = _records("jetson-bringup", with_pass=4, with_fail=0, without_pass=1, without_fail=3)
    metric = evaluate_skills(records)[0]
    assert metric.pass_lift == pytest.approx(0.75)
    assert metric.verdict == "promote"


def test_retire_no_lift_skill() -> None:
    # Identical pass-rate with and without, no loop benefit -> retire.
    records = _records("useless", with_pass=2, with_fail=2, without_pass=2, without_fail=2)
    metric = evaluate_skills(records)[0]
    assert metric.pass_lift == pytest.approx(0.0)
    assert metric.verdict == "retire"


def test_promote_on_loop_reduction() -> None:
    # Same pass-rate but far fewer loops with the skill -> promote.
    records = _records(
        "fast",
        with_pass=4,
        with_fail=0,
        without_pass=4,
        without_fail=0,
        with_loops=2,
        without_loops=6,
    )
    metric = evaluate_skills(records)[0]
    assert metric.loop_delta < 0
    assert metric.verdict == "promote"


def test_insufficient_data() -> None:
    records = _records("new", with_pass=1, with_fail=0, without_pass=1, without_fail=0)
    assert evaluate_skills(records)[0].verdict == "insufficient-data"


def test_analyze_lifecycle_report_and_retire_list() -> None:
    records = _records("useless", with_pass=2, with_fail=2, without_pass=2, without_fail=2)
    report = analyze_lifecycle(records)
    assert report.to_retire == ["useless"]
    assert "retire candidates" in report.render()


def test_load_ablation() -> None:
    data = json.dumps([{"skill": "s", "present": True, "passed": False, "loops": 4}])
    records = load_ablation(data)
    assert records[0].skill == "s" and records[0].loops == 4


# --- reflexion critic -------------------------------------------------------


def test_reflect_classifies_and_gives_heuristic_step() -> None:
    reflexion = reflect("Bash", "pytest failed: 3 tests failed")
    assert reflexion.failure_tag == "unit_test"
    assert reflexion.targeted is False
    assert any("root cause" in s.action for s in reflexion.steps)


def test_reflect_corpus_grounded_is_targeted() -> None:
    corpus = [
        {
            "symptom": "nvcc unsupported gpu arch",
            "root_cause": "sm_87 missing",
            "fix": "add -gencode arch=compute_87,code=sm_87",
            "verification_run_id": "run-9",
        }
    ]
    reflexion = reflect("Bash", "nvcc fatal: unsupported gpu architecture", corpus)
    assert reflexion.targeted is True
    assert reflexion.steps[0].from_corpus is True
    assert "compute_87" in reflexion.steps[0].action
    assert "run-9" in reflexion.steps[0].rationale


def test_reflect_unclassified_still_replans() -> None:
    reflexion = reflect("Bash", "something totally unrecognized happened")
    assert reflexion.steps  # always produces at least one step


class _FakeCorpusClient:
    def __init__(self, tuples: list[dict[str, Any]]) -> None:
        self._tuples = tuples

    async def search_symptom(self, symptom: str, hw: str | None = None) -> list[dict[str, Any]]:
        return self._tuples


def test_reflect_with_corpus() -> None:
    client = _FakeCorpusClient(
        [{"symptom": "s", "root_cause": "c", "fix": "the fix", "verification_run_id": "r"}]
    )
    reflexion = asyncio.run(reflect_with_corpus(client, "Bash", "boom"))  # type: ignore[arg-type]
    assert reflexion.targeted is True
    assert reflexion.corpus_match is not None
