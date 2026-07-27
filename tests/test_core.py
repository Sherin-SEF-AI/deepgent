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


@pytest.fixture(autouse=True)
def _isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The orchestrator writes telemetry under HOME; keep tests off the
    real one."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))


@pytest.mark.unit
def test_options_set_all_section_7_fields(settings: DeepgentSettings, tmp_path: Path) -> None:
    options = Orchestrator(settings=settings, cwd=tmp_path).build_options()
    assert options.allowed_tools == orchestrator_module.MAIN_SESSION_TOOLS
    assert options.disallowed_tools == []
    assert options.permission_mode == settings.permission_mode
    assert isinstance(options.mcp_servers, dict) and "board_farm" in options.mcp_servers
    assert options.agents is not None and len(options.agents) == 5
    assert options.hooks is not None
    assert set(options.hooks) == {
        "UserPromptSubmit",
        "PreToolUse",
        "PostToolUse",
        "PostToolUseFailure",
        "Stop",
        "SubagentStop",
    }
    assert options.setting_sources == ["project"]
    assert options.cwd == tmp_path
    assert options.max_turns == settings.max_turns
    assert options.model == settings.models.sonnet
    # Context assembly synced the skill packs into the session project.
    assert options.skills
    assert (tmp_path / ".claude" / "skills").is_dir()


@pytest.mark.unit
def test_max_turns_override(settings: DeepgentSettings, tmp_path: Path) -> None:
    options = Orchestrator(settings=settings, cwd=tmp_path, max_turns=7).build_options()
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
    settings: DeepgentSettings, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    async def fake_query(**_: Any) -> AsyncIterator[Any]:
        yield AssistantMessage(content=[TextBlock(text="working")], model="m")
        yield _result_message()

    monkeypatch.setattr(orchestrator_module, "_run_query", fake_query)
    outcome = _run(Orchestrator(settings=settings, cwd=tmp_path), "build it")
    assert outcome.result == "done: artifact built"
    assert outcome.is_error is False
    assert outcome.num_turns == 3
    assert outcome.total_cost_usd == 0.42
    assert outcome.session_id == "sess-test"


@pytest.mark.unit
def test_run_task_feeds_budget_tracker(
    settings: DeepgentSettings, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
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
    _run(Orchestrator(settings=settings, cwd=tmp_path), "build it")
    assert trackers, "orchestrator never fed the budget tracker"
    assert trackers[0].spent_usd == pytest.approx(settings.pricing.sonnet.output)


@pytest.mark.unit
def test_run_task_without_result_raises(
    settings: DeepgentSettings, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    async def fake_query(**_: Any) -> AsyncIterator[Any]:
        yield AssistantMessage(content=[TextBlock(text="interrupted")], model="m")

    monkeypatch.setattr(orchestrator_module, "_run_query", fake_query)
    with pytest.raises(TaskExecutionError, match="without a result"):
        _run(Orchestrator(settings=settings, cwd=tmp_path), "build it")


def _run(orchestrator: Orchestrator, task: str) -> Any:
    import asyncio

    return asyncio.run(orchestrator.run_task(task))


@pytest.mark.unit
def test_run_task_emits_tool_events(
    settings: DeepgentSettings, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import asyncio

    from claude_agent_sdk import ToolResultBlock, ToolUseBlock, UserMessage

    from deepgent.core import TaskEvent

    async def fake_query(**_: Any) -> AsyncIterator[Any]:
        yield AssistantMessage(
            content=[ToolUseBlock(id="t1", name="Edit", input={"file_path": "src/a.py"})],
            model="m",
        )
        yield UserMessage(content=[ToolResultBlock(tool_use_id="t1", content="ok", is_error=False)])
        yield _result_message()

    monkeypatch.setattr(orchestrator_module, "_run_query", fake_query)
    events: list[TaskEvent] = []
    orchestrator = Orchestrator(settings=settings, cwd=tmp_path)
    asyncio.run(orchestrator.run_task("edit it", on_event=events.append))
    assert [e.kind for e in events] == ["tool_use", "tool_result"]
    assert events[0].name == "Edit" and events[0].detail == "src/a.py"
    assert events[1].name == "Edit" and events[1].is_error is False


# --- classifier wiring + critic veto (expansion spec A1) --------------------


@pytest.mark.unit
def test_build_options_routes_model_and_agents(settings: DeepgentSettings, tmp_path: Path) -> None:
    from deepgent.core.classifier import classify

    orch = Orchestrator(settings=settings, cwd=tmp_path)
    # A safety task routes to opus and loads the safety auditor + critic.
    options = orch.build_options(classification=classify("safety review of firmware.c"))
    assert options.model == settings.models.opus
    assert options.agents is not None
    assert "safety-auditor" in options.agents and "critic" in options.agents


@pytest.mark.unit
def test_parse_critic_verdict() -> None:
    from deepgent.core import parse_critic_verdict

    assert parse_critic_verdict("looks good\nCRITIC_VERDICT: PASS").vetoed is False
    v = parse_critic_verdict("found a stub\nCRITIC_VERDICT: VETO: contains a placeholder")
    assert v.vetoed is True and "placeholder" in v.reason
    # No verdict line -> fail-open pass.
    assert parse_critic_verdict("no verdict here").vetoed is False


def _two_pass_query(main_error: bool, critic_text: str) -> Any:
    """A fake query that answers the main pass, then the critic pass by prompt."""

    async def fake_query(**kwargs: Any) -> AsyncIterator[Any]:
        prompt = str(kwargs.get("prompt", ""))
        if "CRITIC_VERDICT" in prompt:  # the critic pass
            yield AssistantMessage(content=[TextBlock(text="auditing")], model="m")
            yield _result_message(result=critic_text, session_id="sess-critic")
        else:  # the main pass
            yield AssistantMessage(content=[TextBlock(text="working")], model="m")
            yield _result_message(is_error=main_error, result="done")

    return fake_query


@pytest.mark.unit
def test_critic_veto_turns_success_into_error(
    settings: DeepgentSettings, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        orchestrator_module,
        "_run_query",
        _two_pass_query(main_error=False, critic_text="CRITIC_VERDICT: VETO: found a stub"),
    )
    # "optimize the tensorrt latency" -> risk tier 2 -> critic runs.
    outcome = _run(Orchestrator(settings=settings, cwd=tmp_path), "optimize the tensorrt latency")
    assert outcome.is_error is True
    assert "CRITIC VETO" in outcome.result and "found a stub" in outcome.result


@pytest.mark.unit
def test_critic_pass_leaves_success(
    settings: DeepgentSettings, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        orchestrator_module,
        "_run_query",
        _two_pass_query(main_error=False, critic_text="CRITIC_VERDICT: PASS"),
    )
    outcome = _run(Orchestrator(settings=settings, cwd=tmp_path), "optimize the tensorrt latency")
    assert outcome.is_error is False


@pytest.mark.unit
def test_low_risk_task_skips_critic(
    settings: DeepgentSettings, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[str] = []

    async def counting_query(**kwargs: Any) -> AsyncIterator[Any]:
        calls.append(str(kwargs.get("prompt", "")))
        yield AssistantMessage(content=[TextBlock(text="working")], model="m")
        yield _result_message()

    monkeypatch.setattr(orchestrator_module, "_run_query", counting_query)
    _run(Orchestrator(settings=settings, cwd=tmp_path), "rename a local variable")
    # Generic risk-1 task: one pass only, no critic.
    assert len(calls) == 1
