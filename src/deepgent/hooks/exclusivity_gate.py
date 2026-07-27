"""exclusivity_gate: PreToolUse hook enforcing the delegation contract.

Tool exclusivity (expansion spec A1) is a hard boundary, not a convention:
only the researcher (and the read-only architect) may query the knowledge
layer, and only the hardware-runner may touch boards. The Claude Agent SDK
attributes each sub-agent tool call with agent_type, so a violation is denied
here rather than trusted to prompt discipline.

The main thread (no agent_type) and any agent whose own tool grant already
excludes these tools are unaffected; this hook is defense in depth on top of
the per-agent tool lists.
"""

from typing import Any, cast

import structlog
from claude_agent_sdk.types import (
    HookContext,
    HookInput,
    PreToolUseHookInput,
    SyncHookJSONOutput,
)

from deepgent.agents.definitions import BOARD_FARM_MCP, KNOWLEDGE_MCP

_logger = structlog.get_logger(__name__)

# agent_type values allowed to use each exclusive tool namespace.
_KNOWLEDGE_OWNERS = frozenset({"researcher", "architect"})
_BOARD_OWNERS = frozenset({"hardware-runner"})


def _deny(tool_name: str, agent_type: str, owners: frozenset[str]) -> SyncHookJSONOutput:
    allowed = " or ".join(sorted(owners))
    _logger.warning(
        "exclusivity_violation", tool=tool_name, agent=agent_type, allowed=sorted(owners)
    )
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": (
                f"tool '{tool_name}' is exclusive to {allowed}; the '{agent_type}' "
                "agent must delegate this instead of calling it directly "
                "(delegation contract, expansion spec A1)"
            ),
        }
    }


async def exclusivity_gate(
    input_data: HookInput,
    tool_use_id: str | None,
    context: HookContext,
) -> SyncHookJSONOutput:
    """Deny knowledge/board tool calls from agents that do not own them."""
    data = cast(PreToolUseHookInput, input_data)
    tool_name = data["tool_name"]
    # agent_type is present only inside a sub-agent; absent on the main thread.
    agent_type = cast("dict[str, Any]", data).get("agent_type")
    if not isinstance(agent_type, str) or not agent_type:
        return {}

    if tool_name.startswith(KNOWLEDGE_MCP) and agent_type not in _KNOWLEDGE_OWNERS:
        return _deny(tool_name, agent_type, _KNOWLEDGE_OWNERS)
    if tool_name.startswith(BOARD_FARM_MCP) and agent_type not in _BOARD_OWNERS:
        return _deny(tool_name, agent_type, _BOARD_OWNERS)
    return {}
