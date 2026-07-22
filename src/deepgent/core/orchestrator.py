"""One-shot task orchestration over the Claude Agent SDK."""

from dataclasses import dataclass
from pathlib import Path

import structlog
from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    TextBlock,
    query,
)

from deepgent.agents import build_agent_definitions
from deepgent.config import DeepgentSettings
from deepgent.core.budget import BudgetTracker
from deepgent.errors import TaskExecutionError
from deepgent.hooks import build_hooks

_logger = structlog.get_logger(__name__)

# Seam for tests: monkeypatch deepgent.core.orchestrator._run_query.
_run_query = query

MAIN_SESSION_TOOLS = [
    "Task",
    "Read",
    "Glob",
    "Grep",
    "Bash",
    "Write",
    "Edit",
]


@dataclass(frozen=True)
class TaskOutcome:
    """Result of a one-shot task run."""

    result: str
    is_error: bool
    num_turns: int
    total_cost_usd: float | None
    session_id: str


class Orchestrator:
    """Runs tasks through query() with explicitly pinned session options."""

    def __init__(
        self,
        settings: DeepgentSettings,
        cwd: Path,
        max_turns: int | None = None,
    ) -> None:
        self._settings = settings
        self._cwd = cwd
        self._max_turns = max_turns if max_turns is not None else settings.max_turns

    def build_options(self, tracker: BudgetTracker | None = None) -> ClaudeAgentOptions:
        """Session options with every field from CLAUDE.md section 7 set
        explicitly; nothing relies on ambient defaults."""
        if tracker is None:
            tracker = BudgetTracker(self._settings)
        return ClaudeAgentOptions(
            allowed_tools=list(MAIN_SESSION_TOOLS),
            disallowed_tools=[],
            permission_mode=self._settings.permission_mode,
            mcp_servers={},
            agents=build_agent_definitions(self._settings),
            hooks=build_hooks(self._settings, tracker),
            setting_sources=["project"],
            cwd=self._cwd,
            max_turns=self._max_turns,
            # Deterministic intake routing (section 9) arrives with the
            # classifier; until then every task runs on the sonnet tier.
            model=self._settings.models.sonnet,
        )

    async def run_task(self, task: str) -> TaskOutcome:
        """Run a single task to completion and return its outcome."""
        tracker = BudgetTracker(self._settings)
        options = self.build_options(tracker)
        log = _logger.bind(cwd=str(self._cwd), model=options.model)
        log.info("task_started", task=task)

        result: ResultMessage | None = None
        async for message in _run_query(prompt=task, options=options):
            if isinstance(message, AssistantMessage):
                tracker.record_usage(message.model, message.usage)
                for block in message.content:
                    if isinstance(block, TextBlock):
                        log.debug("assistant_text", text=block.text)
            elif isinstance(message, ResultMessage):
                result = message

        if result is None:
            raise TaskExecutionError(
                "task ended without a result message; the session was likely "
                "interrupted before completion"
            )

        log.info(
            "task_finished",
            is_error=result.is_error,
            num_turns=result.num_turns,
            total_cost_usd=result.total_cost_usd,
        )
        return TaskOutcome(
            result=result.result or "",
            is_error=result.is_error,
            num_turns=result.num_turns,
            total_cost_usd=result.total_cost_usd,
            session_id=result.session_id,
        )
