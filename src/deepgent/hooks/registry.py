"""Hook registrations applied to every session (section 10)."""

from claude_agent_sdk import HookMatcher
from claude_agent_sdk.types import HookEvent

from deepgent.config import DeepgentSettings
from deepgent.core.budget import BudgetTracker
from deepgent.hooks.budget_guard import make_budget_guard
from deepgent.hooks.fact_guard import KNOWLEDGE_TOOL_PREFIX, fact_guard
from deepgent.hooks.misra_gate import make_misra_gate
from deepgent.hooks.safety_gate import BOARD_FARM_TOOL_PREFIX, make_safety_gate
from deepgent.hooks.scope_lock import scope_lock
from deepgent.hooks.telemetry_tap import make_telemetry_tap
from deepgent.telemetry import TelemetryStore


def build_hooks(
    settings: DeepgentSettings,
    tracker: BudgetTracker,
    telemetry_store: TelemetryStore | None = None,
) -> dict[HookEvent, list[HookMatcher]]:
    """The enforcement hooks registered on every session."""
    hooks: dict[HookEvent, list[HookMatcher]] = {
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
            HookMatcher(matcher=f"{KNOWLEDGE_TOOL_PREFIX}.*", hooks=[fact_guard]),
        ],
    }
    if telemetry_store is not None and settings.telemetry_enabled:
        tap = make_telemetry_tap(telemetry_store, board=settings.default_board)
        hooks["PostToolUseFailure"] = [HookMatcher(hooks=[tap])]
        hooks["Stop"] = [HookMatcher(hooks=[tap])]
        hooks["SubagentStop"] = [HookMatcher(hooks=[tap])]
    return hooks
