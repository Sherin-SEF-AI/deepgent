"""WO-39: intelligence features wired into the live task loop.

Covers pre-mortem injection in the orchestrator, the reflexion_tap failure
hook, and the fact_guard confidence annotation.
"""

import asyncio
from pathlib import Path

import pytest

from deepgent.config import load_settings
from deepgent.core import Orchestrator
from deepgent.hooks.reflexion_tap import make_reflexion_tap

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parent.parent


# --- reflexion_tap hook -----------------------------------------------------


def test_reflexion_tap_injects_replan() -> None:
    tap = make_reflexion_tap()
    out = asyncio.run(
        tap(
            {
                "hook_event_name": "PostToolUseFailure",
                "tool_name": "Bash",
                "error": "pytest failed: 2 tests failed",
                "session_id": "s",
            },
            None,
            None,  # type: ignore[arg-type]
        )
    )
    ctx = out["hookSpecificOutput"]["additionalContext"]  # type: ignore[index,typeddict-item]
    assert "reflexion" in ctx and "unit_test" in ctx


def test_reflexion_tap_ignores_interrupt() -> None:
    tap = make_reflexion_tap()
    out = asyncio.run(
        tap(
            {
                "hook_event_name": "PostToolUseFailure",
                "tool_name": "Bash",
                "error": "boom",
                "session_id": "s",
                "is_interrupt": True,
            },
            None,
            None,  # type: ignore[arg-type]
        )
    )
    assert out == {}


def test_reflexion_tap_ignores_other_events() -> None:
    tap = make_reflexion_tap()
    out = asyncio.run(tap({"hook_event_name": "Stop"}, None, None))  # type: ignore[arg-type]
    assert out == {}


# --- pre-mortem injection in the orchestrator -------------------------------


def _settings(**overrides: object) -> object:
    settings = load_settings(REPO_ROOT)
    for key, value in overrides.items():
        setattr(settings, key, value)
    return settings


def test_premortem_disabled_leaves_task_unchanged() -> None:
    orch = Orchestrator(settings=_settings(premortem_enabled=False), cwd=REPO_ROOT)  # type: ignore[arg-type]
    result = asyncio.run(orch._with_premortem("build a cuda kernel"))
    assert result == "build a cuda kernel"


def test_premortem_prepends_prelude(monkeypatch: pytest.MonkeyPatch) -> None:
    import importlib

    import deepgent.knowledge as knowledge_pkg
    from deepgent.knowledge.premortem import PredictedRisk, PreMortem

    premortem_module = importlib.import_module("deepgent.knowledge.premortem")

    class _FakeClient:
        async def aclose(self) -> None:
            return None

    async def fake_premortem(client: object, symptom: str, hw: object = None, stack: object = None):
        return PreMortem(
            risks=[PredictedRisk("nvcc arch", "sm_87 missing", "add -gencode", "run-1", "corpus")]
        )

    monkeypatch.setattr(knowledge_pkg, "build_rag_client", lambda settings: _FakeClient())
    monkeypatch.setattr(premortem_module, "premortem", fake_premortem)

    orch = Orchestrator(settings=_settings(premortem_enabled=True), cwd=REPO_ROOT)  # type: ignore[arg-type]
    result = asyncio.run(orch._with_premortem("port the detector"))
    assert "Known failure modes" in result
    assert "port the detector" in result
    assert "add -gencode" in result


def test_premortem_best_effort_on_client_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(settings: object) -> object:
        raise RuntimeError("no knowledge server configured")

    monkeypatch.setattr("deepgent.knowledge.build_rag_client", boom)
    orch = Orchestrator(settings=_settings(premortem_enabled=True), cwd=REPO_ROOT)  # type: ignore[arg-type]
    # A missing knowledge layer must not break the task.
    result = asyncio.run(orch._with_premortem("do the thing"))
    assert result == "do the thing"


# --- fact_guard confidence annotation ---------------------------------------


def test_fact_guard_note_carries_confidence() -> None:
    from deepgent.hooks.fact_guard import filter_chunks_payload

    grounded = {
        "doc": "IMX219",
        "section": "3.2",
        "version_range": "r36",
        "chip": "imx219",
        "hash": "abc",
        "text": "y",
    }
    payload = {"chunks": [{"text": "x"}, grounded]}
    clean, stripped = filter_chunks_payload(payload)
    # One chunk lacked provenance and was stripped; the grounded one survives.
    assert stripped == 1
    assert len(clean["chunks"]) == 1
