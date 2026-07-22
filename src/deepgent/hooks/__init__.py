"""Enforcement layer: hook callbacks for scope lock, safety gates, lint gates,
budgets, and telemetry taps."""

from deepgent.hooks.budget_guard import make_budget_guard
from deepgent.hooks.misra_gate import Finding, is_gated_file, make_misra_gate
from deepgent.hooks.registry import build_hooks
from deepgent.hooks.safety_gate import (
    BOARD_FARM_TOOL_PREFIX,
    gated_op_tag,
    make_safety_gate,
)
from deepgent.hooks.scope_lock import REFUSAL, is_in_scope, scope_lock

__all__ = [
    "BOARD_FARM_TOOL_PREFIX",
    "REFUSAL",
    "Finding",
    "build_hooks",
    "gated_op_tag",
    "is_gated_file",
    "is_in_scope",
    "make_budget_guard",
    "make_misra_gate",
    "make_safety_gate",
    "scope_lock",
]
