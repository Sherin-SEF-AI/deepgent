"""Telemetry: sqlite store, record schemas, and exporters feeding the data flywheel."""

from deepgent.telemetry.sanitizer import sanitize_mapping, sanitize_text
from deepgent.telemetry.store import (
    FAILURE_TAGS,
    CorpusCandidate,
    FailureEvent,
    TaskRecord,
    TelemetryStore,
    TelemetrySummary,
    default_db_path,
)
from deepgent.telemetry.taxonomy import classify_failure

__all__ = [
    "FAILURE_TAGS",
    "CorpusCandidate",
    "FailureEvent",
    "TaskRecord",
    "TelemetryStore",
    "TelemetrySummary",
    "classify_failure",
    "default_db_path",
    "sanitize_mapping",
    "sanitize_text",
]
