"""telemetry_tap: Stop/SubagentStop/PostToolUseFailure hook (section 10).

Persists sanitized failure events as they happen and, at session stop,
drafts a corpus tuple candidate when the session recovered from earlier
failures (a failed-to-passed transition). Candidates wait for owner
approval; nothing uploads anywhere from here.
"""

from typing import Any, cast

import structlog
from claude_agent_sdk.types import (
    HookContext,
    HookInput,
    PostToolUseFailureHookInput,
    SyncHookJSONOutput,
)

from deepgent.config import load_versions
from deepgent.errors import ConfigError
from deepgent.telemetry.store import CorpusCandidate, FailureEvent, TelemetryStore, now
from deepgent.telemetry.taxonomy import classify_failure

_logger = structlog.get_logger(__name__)


def _session_versions() -> dict[str, Any]:
    try:
        versions = load_versions()
        return {"jetson": versions.get("jetson", {}), "ros2": versions.get("ros2", {})}
    except ConfigError:
        return {}


def make_telemetry_tap(store: TelemetryStore, board: str | None = None) -> Any:
    """Build the telemetry_tap callback bound to one store."""

    async def telemetry_tap(
        input_data: HookInput,
        tool_use_id: str | None,
        context: HookContext,
    ) -> SyncHookJSONOutput:
        event_name = input_data["hook_event_name"]
        if event_name == "PostToolUseFailure":
            failure = cast(PostToolUseFailureHookInput, input_data)
            if failure.get("is_interrupt"):
                return {}
            store.record_failure(
                FailureEvent(
                    session_id=failure["session_id"],
                    ts=now(),
                    tool_name=failure["tool_name"],
                    error=failure["error"],
                    agent_type=failure.get("agent_type"),
                    failure_tag=classify_failure(failure["tool_name"], failure["error"]),
                )
            )
            return {}

        if event_name == "Stop":
            session_id = input_data["session_id"]
            failures = store.failures_for_session(session_id)
            if failures:
                # The session finished after earlier failures: draft a
                # candidate tuple from the first symptom (docs/schemas.md).
                store.draft_corpus_candidate(
                    CorpusCandidate(
                        session_id=session_id,
                        ts=now(),
                        symptom=failures[0].error,
                        hw_config=board,
                        versions=_session_versions(),
                    )
                )
        return {}

    return telemetry_tap
