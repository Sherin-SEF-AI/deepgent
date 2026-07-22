"""safety_gate: PreToolUse hook on board-farm tools (section 10).

Operations tagged flash, gpio, power, daemon-restart, or fs-destructive
require interactive approval unless whitelisted in .deepgent/gates.toml.
CI mode auto-denies anything not whitelisted.
"""

import re
import tomllib
from pathlib import Path
from typing import Any, cast

import structlog
from claude_agent_sdk.types import (
    HookContext,
    HookInput,
    PreToolUseHookInput,
    SyncHookJSONOutput,
)

from deepgent.config import DeepgentSettings

_logger = structlog.get_logger(__name__)

BOARD_FARM_TOOL_PREFIX = "mcp__board_farm__"
GATES_RELPATH = Path(".deepgent") / "gates.toml"

# Board-farm tools that are gated purely by name (section 12 tags them).
_TOOL_TAGS = {
    "power": "power",
    "flash": "flash",
    "gpio": "gpio",
}

_DAEMON_RESTART_PATTERNS = tuple(
    re.compile(pattern)
    for pattern in (
        r"\bsystemctl\s+(restart|stop|disable|mask)\b",
        r"\bservice\s+\S+\s+(restart|stop)\b",
        r"\breboot\b",
        r"\bshutdown\b",
        r"\binit\s+[06]\b",
    )
)

_FS_DESTRUCTIVE_PATTERNS = tuple(
    re.compile(pattern)
    for pattern in (
        r"\brm\s+-[a-z-]*[rf]",
        r"\bmkfs",
        r"\bdd\b.*\bof=/dev/",
        r"\b(parted|fdisk|sgdisk)\b",
        r">\s*/dev/",
        r"\btruncate\s+-s\s+0\b",
    )
)


def gated_op_tag(tool_name: str, tool_input: dict[str, Any]) -> str | None:
    """Return the section 10 op tag for a board-farm call, or None if ungated."""
    short_name = tool_name.removeprefix(BOARD_FARM_TOOL_PREFIX)
    if short_name in _TOOL_TAGS:
        return _TOOL_TAGS[short_name]
    if short_name == "exec":
        command = str(tool_input.get("command", ""))
        if any(pattern.search(command) for pattern in _DAEMON_RESTART_PATTERNS):
            return "daemon-restart"
        if any(pattern.search(command) for pattern in _FS_DESTRUCTIVE_PATTERNS):
            return "fs-destructive"
    return None


def _whitelisted(cwd: Path, board: str | None, op_tag: str) -> bool:
    """True when .deepgent/gates.toml allows op_tag for this board."""
    if board is None:
        return False
    gates_path = cwd / GATES_RELPATH
    if not gates_path.is_file():
        return False
    try:
        with gates_path.open("rb") as f:
            gates = tomllib.load(f)
    except tomllib.TOMLDecodeError:
        _logger.warning("gates_toml_invalid", path=str(gates_path))
        return False
    allowed = gates.get("boards", {}).get(board, {}).get("allow", [])
    return isinstance(allowed, list) and op_tag in allowed


def make_safety_gate(
    settings: DeepgentSettings,
) -> Any:
    """Build the safety_gate callback with CI mode resolved from settings."""

    async def safety_gate(
        input_data: HookInput,
        tool_use_id: str | None,
        context: HookContext,
    ) -> SyncHookJSONOutput:
        data = cast(PreToolUseHookInput, input_data)
        tool_name = data["tool_name"]
        if not tool_name.startswith(BOARD_FARM_TOOL_PREFIX):
            return {}

        tool_input = data["tool_input"]
        op_tag = gated_op_tag(tool_name, tool_input)
        if op_tag is None:
            return {}

        board_value = tool_input.get("board") or tool_input.get("board_id")
        board = str(board_value) if board_value is not None else None
        if _whitelisted(Path(data["cwd"]), board, op_tag):
            return {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "allow",
                    "permissionDecisionReason": (
                        f"gated op '{op_tag}' whitelisted for board '{board}' in {GATES_RELPATH}"
                    ),
                }
            }

        if settings.ci:
            return {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": (
                        f"gated op '{op_tag}' on board '{board}' denied in CI "
                        f"mode; whitelist it in {GATES_RELPATH} to allow"
                    ),
                }
            }
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "ask",
                "permissionDecisionReason": (
                    f"gated op '{op_tag}' on board '{board}' requires approval"
                ),
            }
        }

    return safety_gate
