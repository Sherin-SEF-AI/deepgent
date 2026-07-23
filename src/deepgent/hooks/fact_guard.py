"""fact_guard: PostToolUse hook on knowledge tools (section 10).

Every RAG answer must carry provenance fields; chunks that lack any of them
are stripped from the tool output and the strip is flagged to the model, so
an unprovenanced "fact" can never silently enter a session.
"""

import json
from typing import Any, cast

import structlog
from claude_agent_sdk.types import (
    HookContext,
    HookInput,
    PostToolUseHookInput,
    SyncHookJSONOutput,
)

from deepgent.knowledge.fact_confidence import confidence_for
from deepgent.knowledge.rag import PROVENANCE_FIELDS

_logger = structlog.get_logger(__name__)

KNOWLEDGE_TOOL_PREFIX = "mcp__knowledge__"
# Surviving RAG facts are datasheet-grounded; their calibrated confidence tier
# (#12). Empirical on-target verification is the only thing that reaches 1.0.
_RAG_CONFIDENCE = confidence_for("datasheet_rag")


def has_provenance(chunk: dict[str, Any]) -> bool:
    return all(chunk.get(field) for field in PROVENANCE_FIELDS)


def filter_chunks_payload(payload: dict[str, Any]) -> tuple[dict[str, Any], int]:
    """Strip unprovenanced chunks; return (clean payload, stripped count)."""
    chunks = payload.get("chunks")
    if not isinstance(chunks, list):
        return payload, 0
    kept = [c for c in chunks if isinstance(c, dict) and has_provenance(c)]
    stripped = len(chunks) - len(kept)
    if stripped:
        payload = {**payload, "chunks": kept, "unknown": len(kept) == 0}
    return payload, stripped


def _extract_text(tool_response: Any) -> str | None:
    """The text body of an MCP tool response, if it has one."""
    if isinstance(tool_response, dict):
        content = tool_response.get("content")
        if isinstance(content, list) and content:
            first = content[0]
            if isinstance(first, dict) and isinstance(first.get("text"), str):
                return str(first["text"])
    if isinstance(tool_response, str):
        return tool_response
    return None


async def fact_guard(
    input_data: HookInput,
    tool_use_id: str | None,
    context: HookContext,
) -> SyncHookJSONOutput:
    """Strip and flag knowledge results that lack provenance."""
    data = cast(PostToolUseHookInput, input_data)
    if not data["tool_name"].startswith(KNOWLEDGE_TOOL_PREFIX):
        return {}
    text = _extract_text(data.get("tool_response"))
    if text is None:
        return {}
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return {}
    if not isinstance(payload, dict):
        return {}

    clean, stripped = filter_chunks_payload(payload)
    if stripped == 0:
        return {}
    _logger.warning("fact_guard_stripped", count=stripped, tool=data["tool_name"])
    note = (
        f"fact_guard removed {stripped} result(s) lacking provenance "
        f"({', '.join(PROVENANCE_FIELDS)}); treat missing facts as unknown, "
        f"never guess them. Surviving facts are datasheet-grounded (confidence "
        f"~{_RAG_CONFIDENCE:.1f}); only on-target verification raises that to 1.0"
    )
    return {
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "updatedMCPToolOutput": {
                "content": [{"type": "text", "text": json.dumps(clean, indent=2)}]
            },
            "additionalContext": note,
        }
    }
