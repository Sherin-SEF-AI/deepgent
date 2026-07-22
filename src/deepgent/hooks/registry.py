"""Hook registrations applied to every session (section 10)."""

from claude_agent_sdk import HookMatcher
from claude_agent_sdk.types import HookEvent

from deepgent.config import DeepgentSettings
from deepgent.core.budget import BudgetTracker
from deepgent.hooks.budget_guard import make_budget_guard
from deepgent.hooks.misra_gate import make_misra_gate
from deepgent.hooks.safety_gate import BOARD_FARM_TOOL_PREFIX, make_safety_gate
from deepgent.hooks.scope_lock import scope_lock


def build_hooks(
    settings: DeepgentSettings, tracker: BudgetTracker
) -> dict[HookEvent, list[HookMatcher]]:
    """The enforcement hooks registered on every session."""
    return {
        "UserPromptSubmit": [HookMatcher(hooks=[scope_lock])],
        "PreToolUse": [
            HookMatcher(
                matcher=f"{BOARD_FARM_TOOL_PREFIX}.*",
                hooks=[make_safety_gate(settings)],
            )
        ],
        "PostToolUse": [
            HookMatcher(hooks=[make_budget_guard(tracker)]),
            HookMatcher(matcher="Write|Edit", hooks=[make_misra_gate()]),
        ],
    }
