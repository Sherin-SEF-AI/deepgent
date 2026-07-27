"""Tool-exclusivity PreToolUse hook (delegation contract)."""

import asyncio
from typing import Any

import pytest

from deepgent.hooks.exclusivity_gate import exclusivity_gate

pytestmark = pytest.mark.unit


def _run(tool_name: str, agent_type: str | None) -> dict[str, Any]:
    data: dict[str, Any] = {
        "hook_event_name": "PreToolUse",
        "tool_name": tool_name,
        "tool_input": {},
        "cwd": "/tmp",
    }
    if agent_type is not None:
        data["agent_type"] = agent_type
    return asyncio.run(exclusivity_gate(data, None, object()))  # type: ignore[arg-type]


def _decision(out: dict[str, Any]) -> str | None:
    hso = out.get("hookSpecificOutput")
    return hso.get("permissionDecision") if hso else None


def test_researcher_may_query_knowledge() -> None:
    assert _run("mcp__knowledge__search", "researcher") == {}


def test_architect_may_query_knowledge() -> None:
    assert _run("mcp__knowledge__matrix_query", "architect") == {}


def test_implementer_may_not_query_knowledge() -> None:
    out = _run("mcp__knowledge__search", "implementer")
    assert _decision(out) == "deny"
    assert "researcher" in out["hookSpecificOutput"]["permissionDecisionReason"]


def test_hardware_runner_may_touch_boards() -> None:
    assert _run("mcp__board_farm__exec", "hardware-runner") == {}


def test_perception_engineer_may_not_touch_boards() -> None:
    out = _run("mcp__board_farm__flash", "perception-engineer")
    assert _decision(out) == "deny"
    assert "hardware-runner" in out["hookSpecificOutput"]["permissionDecisionReason"]


def test_main_thread_is_unaffected() -> None:
    # No agent_type -> the main loop, which self-restricts via allowed_tools.
    assert _run("mcp__knowledge__search", None) == {}


def test_non_exclusive_tools_pass_through() -> None:
    assert _run("Read", "implementer") == {}
    assert _run("Bash", "verifier") == {}
