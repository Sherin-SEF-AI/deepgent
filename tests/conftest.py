"""Shared test fixtures."""

from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
import structlog
from claude_agent_sdk.types import HookContext

FakeBoardCall = Callable[..., dict[str, Any]]


@pytest.fixture(autouse=True)
def _reset_structlog() -> Iterator[None]:
    """CLI tests configure structlog against CliRunner's captured (and later
    closed) stderr; reset so other tests log to a live stream."""
    yield
    structlog.reset_defaults()


@pytest.fixture
def hook_context() -> HookContext:
    return HookContext(signal=None)


@pytest.fixture
def fake_board_call(tmp_path: Path) -> FakeBoardCall:
    """Fabricate PreToolUse inputs for board-farm tools (section 23: tests
    exercise safety_gate through this fixture, never bypass it)."""

    def _make(
        tool: str,
        tool_input: dict[str, Any] | None = None,
        cwd: Path | None = None,
    ) -> dict[str, Any]:
        return {
            "session_id": "sess-fake",
            "transcript_path": "/tmp/fake-transcript",
            "cwd": str(cwd if cwd is not None else tmp_path),
            "permission_mode": "default",
            "agent_id": "agent-fake",
            "agent_type": "hardware-runner",
            "hook_event_name": "PreToolUse",
            "tool_name": f"mcp__board_farm__{tool}",
            "tool_input": tool_input or {},
            "tool_use_id": "toolu-fake",
        }

    return _make
