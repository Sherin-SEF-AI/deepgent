"""Orchestrator option construction and result handling."""

from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest
from claude_agent_sdk import AssistantMessage, ResultMessage, TextBlock

import deepgent.core.orchestrator as orchestrator_module
from deepgent.config import DeepgentSettings, load_settings
from deepgent.core import Orchestrator
from deepgent.errors import TaskExecutionError

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def settings() -> DeepgentSettings:
    return load_settings(REPO_ROOT)


@pytest.mark.unit
def test_options_set_all_section_7_fields(settings: DeepgentSettings) -> None:
    options = Orchestrator(settings=settings, cwd=REPO_ROOT).build_options()
    assert options.allowed_tools == orchestrator_module.MAIN_SESSION_TOOLS
    assert options.disallowed_tools == []
    assert options.permission_mode == settings.permission_mode
    assert options.mcp_servers == {}
    assert options.agents is not None and len(options.agents) == 5
    assert options.hooks is not None
    assert set(options.hooks) == {"UserPromptSubmit", "PreToolUse", "PostToolUse"}
    assert options.setting_sources == ["project"]
    assert options.cwd == REPO_ROOT
    assert options.max_turns == settings.max_turns
    assert options.model == settings.models.sonnet


@pytest.mark.unit
def test_max_turns_override(settings: DeepgentSettings) -> None:
    options = Orchestrator(settings=settings, cwd=REPO_ROOT, max_turns=7).build_options()
    assert options.max_turns == 7


def _result_message(**overrides: Any) -> ResultMessage:
    fields: dict[str, Any] = {
        "subtype": "success",
        "duration_ms": 1200,
        "duration_api_ms": 900,
        "is_error": False,
        "num_turns": 3,
        "session_id": "sess-test",
        "total_cost_usd": 0.42,
        "result": "done: artifact built",
    }
    fields.update(overrides)
    return ResultMessage(**fields)


@pytest.mark.unit
def test_run_task_returns_outcome(
    settings: DeepgentSettings, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_query(**_: Any) -> AsyncIterator[Any]:
        yield AssistantMessage(content=[TextBlock(text="working")], model="m")
        yield _result_message()

    monkeypatch.setattr(orchestrator_module, "_run_query", fake_query)
    outcome = _run(Orchestrator(settings=settings, cwd=REPO_ROOT), "build it")
    assert outcome.result == "done: artifact built"
    assert outcome.is_error is False
    assert outcome.num_turns == 3
    assert outcome.total_cost_usd == 0.42
    assert outcome.session_id == "sess-test"


@pytest.mark.unit
def test_run_task_feeds_budget_tracker(
    settings: DeepgentSettings, monkeypatch: pytest.MonkeyPatch
) -> None:
    from deepgent.core.budget import BudgetTracker

    async def fake_query(**_: Any) -> AsyncIterator[Any]:
        yield AssistantMessage(
            content=[TextBlock(text="working")],
            model=settings.models.sonnet,
            usage={"output_tokens": 1_000_000},
        )
        yield _result_message()

    trackers: list[BudgetTracker] = []
    original = BudgetTracker.record_usage

    def spy(self: BudgetTracker, model: str, usage: Any) -> None:
        trackers.append(self)
        original(self, model, usage)

    monkeypatch.setattr(orchestrator_module, "_run_query", fake_query)
    monkeypatch.setattr(BudgetTracker, "record_usage", spy)
    _run(Orchestrator(settings=settings, cwd=REPO_ROOT), "build it")
    assert trackers, "orchestrator never fed the budget tracker"
    assert trackers[0].spent_usd == pytest.approx(settings.pricing.sonnet.output)


@pytest.mark.unit
def test_run_task_without_result_raises(
    settings: DeepgentSettings, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_query(**_: Any) -> AsyncIterator[Any]:
        yield AssistantMessage(content=[TextBlock(text="interrupted")], model="m")

    monkeypatch.setattr(orchestrator_module, "_run_query", fake_query)
    with pytest.raises(TaskExecutionError, match="without a result"):
        _run(Orchestrator(settings=settings, cwd=REPO_ROOT), "build it")


def _run(orchestrator: Orchestrator, task: str) -> Any:
    import asyncio

    return asyncio.run(orchestrator.run_task(task))
