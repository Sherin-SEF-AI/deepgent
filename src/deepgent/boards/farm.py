"""board-farm in-process MCP server (docs/mcp.md).

Tools: list_boards, lease, release, deploy, exec, capture_metrics, power.
Destructive operations are tagged for safety_gate (hooks/safety_gate.py),
which sees them as mcp__board_farm__<tool>. Mutating tools require an
active lease held by this server instance; only the hardware-runner
subagent is granted these tools (section 8).
"""

import json
from pathlib import Path
from typing import Any

import structlog
from claude_agent_sdk import SdkMcpTool, create_sdk_mcp_server, tool
from claude_agent_sdk.types import McpSdkServerConfig

from deepgent.boards.leases import (
    DEFAULT_LEASE_TTL_S,
    acquire_lease,
    current_lease,
    new_holder_id,
    release_lease,
    require_lease,
)
from deepgent.boards.registry import get_board, load_registry
from deepgent.boards.runner import BoardRunner
from deepgent.boards.tegrastats import parse_capture
from deepgent.errors import DeepgentError

_logger = structlog.get_logger(__name__)

SERVER_NAME = "board_farm"
_MAX_EXEC_TIMEOUT_S = 600.0
_MAX_CAPTURE_S = 300.0


def _ok(payload: Any) -> dict[str, Any]:
    text = payload if isinstance(payload, str) else json.dumps(payload, indent=2)
    return {"content": [{"type": "text", "text": text}]}


def _err(message: str) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": message}], "is_error": True}


def build_board_farm_tools(holder: str | None = None) -> list[SdkMcpTool[Any]]:
    """Create the board-farm tool set bound to one lease holder identity."""
    holder_id = holder if holder is not None else new_holder_id()

    @tool(
        "list_boards",
        "List registered target boards and their lease state.",
        {},
    )
    async def list_boards(args: dict[str, Any]) -> dict[str, Any]:
        boards = []
        for board in load_registry().values():
            lease = current_lease(board.id)
            boards.append(
                {
                    "id": board.id,
                    "type": board.type,
                    "l4t": board.l4t,
                    "capabilities": board.capabilities,
                    "power_ctl": board.power_ctl,
                    "leased_by": lease.holder if lease else None,
                }
            )
        return _ok({"boards": boards})

    @tool(
        "lease",
        "Lease a board for exclusive use. Required before deploy/exec/"
        "capture_metrics/power. Leases auto-expire.",
        {"board": str},
    )
    async def lease_tool(args: dict[str, Any]) -> dict[str, Any]:
        try:
            board = get_board(str(args["board"]))
            lease = acquire_lease(board.id, holder_id, DEFAULT_LEASE_TTL_S)
        except DeepgentError as exc:
            return _err(str(exc))
        return _ok(
            {
                "board": lease.board_id,
                "holder": lease.holder,
                "expires_in_s": round(lease.expires_at - lease.acquired_at),
            }
        )

    @tool(
        "release",
        "Release a previously leased board, restoring it for other tasks.",
        {"board": str},
    )
    async def release_tool(args: dict[str, Any]) -> dict[str, Any]:
        try:
            release_lease(str(args["board"]), holder_id)
        except DeepgentError as exc:
            return _err(str(exc))
        return _ok(f"released board '{args['board']}'")

    @tool(
        "deploy",
        "Copy a local file to the leased board over SFTP.",
        {"board": str, "local_path": str, "remote_path": str},
    )
    async def deploy(args: dict[str, Any]) -> dict[str, Any]:
        local = Path(str(args["local_path"]))
        if not local.is_file():
            return _err(f"local file {local} does not exist")
        try:
            board = get_board(str(args["board"]))
            require_lease(board.id, holder_id)
            async with BoardRunner(board) as runner:
                await runner.put(local, str(args["remote_path"]))
        except DeepgentError as exc:
            return _err(str(exc))
        return _ok(f"deployed {local} to {args['board']}:{args['remote_path']}")

    @tool(
        "exec",
        "Run a command on the leased board under a watchdog timeout. "
        "Destructive commands are gated for approval.",
        {"board": str, "command": str, "timeout_s": float},
    )
    async def exec_tool(args: dict[str, Any]) -> dict[str, Any]:
        timeout_s = min(float(args.get("timeout_s", 60.0)), _MAX_EXEC_TIMEOUT_S)
        try:
            board = get_board(str(args["board"]))
            require_lease(board.id, holder_id)
            async with BoardRunner(board) as runner:
                result = await runner.run(str(args["command"]), timeout_s=timeout_s)
        except DeepgentError as exc:
            return _err(str(exc))
        # A nonzero exit is a completed tool call with a failing command; the
        # agent interprets exit_status, so is_error stays unset here.
        return _ok(
            {
                "exit_status": result.exit_status,
                "timed_out": result.timed_out,
                "stdout": result.stdout[-8000:],
                "stderr": result.stderr[-8000:],
            }
        )

    @tool(
        "capture_metrics",
        "Capture tegrastats on the leased board for a duration and return parsed summary metrics.",
        {"board": str, "duration_s": float},
    )
    async def capture_metrics(args: dict[str, Any]) -> dict[str, Any]:
        duration_s = min(float(args.get("duration_s", 10.0)), _MAX_CAPTURE_S)
        try:
            board = get_board(str(args["board"]))
            require_lease(board.id, holder_id)
            async with BoardRunner(board) as runner:
                raw = await runner.capture_tegrastats(duration_s)
        except DeepgentError as exc:
            return _err(str(exc))
        capture = parse_capture(raw)
        return _ok({"metrics": capture.summary_metrics(), "raw_lines": len(raw.splitlines())})

    @tool(
        "power",
        "Power-cycle or switch a board (gated operation requiring approval).",
        {"board": str, "action": str},
    )
    async def power(args: dict[str, Any]) -> dict[str, Any]:
        try:
            board = get_board(str(args["board"]))
            require_lease(board.id, holder_id)
        except DeepgentError as exc:
            return _err(str(exc))
        if board.power_ctl == "none":
            return _err(
                f"board '{board.id}' has power_ctl=none; no power control "
                "hardware is configured for it"
            )
        # smartplug/pdu drivers arrive with the physical hardware; refusing
        # honestly beats pretending the action happened.
        return _err(
            f"power_ctl '{board.power_ctl}' driver is not implemented yet; power the board manually"
        )

    _logger.debug("board_farm_tools_built", holder=holder_id)
    return [
        list_boards,
        lease_tool,
        release_tool,
        deploy,
        exec_tool,
        capture_metrics,
        power,
    ]


def build_board_farm_server(holder: str | None = None) -> McpSdkServerConfig:
    """Create the in-process board-farm MCP server."""
    return create_sdk_mcp_server(
        name=SERVER_NAME,
        version="1.0.0",
        tools=build_board_farm_tools(holder),
    )
