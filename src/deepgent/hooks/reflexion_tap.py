"""reflexion_tap: PostToolUseFailure hook injecting a targeted replan (#15).

When a tool call fails, instead of letting the agent retry blindly, classify
the failure against the taxonomy and inject the deterministic, root-cause
replan as additional context so the next attempt is targeted. Corpus-grounded
reflexion (a verified prior fix) is available via the researcher and the
`deepgent reflect` command; this in-loop hook stays fast and network-free.
"""

from typing import Any, cast

import structlog
from claude_agent_sdk.types import (
    HookContext,
    HookInput,
    PostToolUseFailureHookInput,
    SyncHookJSONOutput,
)

from deepgent.core.reflexion import reflect

_logger = structlog.get_logger(__name__)


def make_reflexion_tap() -> Any:
    """Build the reflexion_tap callback."""

    async def reflexion_tap(
        input_data: HookInput,
        tool_use_id: str | None,
        context: HookContext,
    ) -> SyncHookJSONOutput:
        if input_data.get("hook_event_name") != "PostToolUseFailure":
            return {}
        failure = cast(PostToolUseFailureHookInput, input_data)
        if failure.get("is_interrupt"):
            return {}
        tool_name = failure.get("tool_name", "")
        error = failure.get("error", "")
        if not error:
            return {}
        reflexion = reflect(str(tool_name), str(error))
        steps = "\n".join(f"- {step.action}" for step in reflexion.steps)
        note = (
            f"reflexion (failure class: {reflexion.failure_tag or 'unclassified'}): "
            f"before retrying, address the root cause:\n{steps}"
        )
        _logger.info("reflexion_tap", failure_tag=reflexion.failure_tag)
        return {
            "hookSpecificOutput": {
                "hookEventName": "PostToolUseFailure",
                "additionalContext": note,
            }
        }

    return reflexion_tap
