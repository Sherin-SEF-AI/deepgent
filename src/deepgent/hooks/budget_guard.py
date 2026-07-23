"""budget_guard: PostToolUse hook enforcing the per-task spend cap (section 9)."""

from typing import Any

import structlog
from claude_agent_sdk.types import HookContext, HookInput, SyncHookJSONOutput

from deepgent.core.budget import HALT_FRACTION, BudgetTracker

_logger = structlog.get_logger(__name__)


def make_budget_guard(tracker: BudgetTracker) -> Any:
    """Build the budget_guard callback bound to one task's tracker."""

    async def budget_guard(
        input_data: HookInput,
        tool_use_id: str | None,
        context: HookContext,
    ) -> SyncHookJSONOutput:
        if not tracker.halt_needed:
            return {}
        calib = ""
        if abs(tracker.calibration - 1.0) > 1e-9:
            calib = f" (calibration x{tracker.calibration:.2f} applied)"
        reason = (
            f"budget guard: estimated spend ${tracker.effective_spent_usd:.2f}"
            f"{calib} reached {HALT_FRACTION:.0%} of the ${tracker.cap_usd:.2f} "
            "per-task cap; halting. Raise budget.per_task_usd or rerun with "
            "--budget to continue."
        )
        _logger.warning(
            "budget_halt",
            effective_spent_usd=tracker.effective_spent_usd,
            raw_spent_usd=tracker.spent_usd,
            calibration=tracker.calibration,
            cap_usd=tracker.cap_usd,
        )
        return {"continue_": False, "stopReason": reason}

    return budget_guard
