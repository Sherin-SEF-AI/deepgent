"""Telemetry store, sanitizer, taxonomy, and telemetry_tap behavior."""

import asyncio
import time
from pathlib import Path
from typing import Any

import pytest
from claude_agent_sdk.types import HookContext

from deepgent.hooks.telemetry_tap import make_telemetry_tap
from deepgent.telemetry import (
    FAILURE_TAGS,
    FailureEvent,
    TaskRecord,
    TelemetryStore,
    classify_failure,
    sanitize_text,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def store(tmp_path: Path) -> TelemetryStore:
    return TelemetryStore(tmp_path / "telemetry.db")


def _task_record(**overrides: Any) -> TaskRecord:
    fields: dict[str, Any] = {
        "id": "sess-1",
        "ts": time.time(),
        "task_class": "task/oneshot",
        "board": "agx-orin",
        "model_mix": {"claude-x": 1200},
        "tokens": 1200,
        "usd": 0.34,
        "wall_s": 42.0,
        "loops": 5,
        "outcome": "success",
    }
    fields.update(overrides)
    return TaskRecord(**fields)


class TestStore:
    @pytest.mark.unit
    def test_task_record_round_trip(self, store: TelemetryStore) -> None:
        store.record_task(_task_record())
        loaded = store.get_task("sess-1")
        assert loaded is not None
        assert loaded.tokens == 1200
        assert loaded.model_mix == {"claude-x": 1200}
        assert store.task_records()[0].id == "sess-1"

    @pytest.mark.unit
    def test_migrates_legacy_db_without_est_usd(self, tmp_path: Path) -> None:
        import sqlite3

        db = tmp_path / "legacy.db"
        conn = sqlite3.connect(db)
        conn.executescript(
            "CREATE TABLE task_records (id TEXT PRIMARY KEY, ts REAL NOT NULL, "
            "task_class TEXT NOT NULL, board TEXT, model_mix TEXT NOT NULL, "
            "tokens INTEGER NOT NULL, usd REAL, wall_s REAL NOT NULL, "
            "loops INTEGER NOT NULL, outcome TEXT NOT NULL, failure_tag TEXT, "
            "artifacts_path TEXT);"
        )
        conn.commit()
        conn.close()
        # Opening the store must add est_usd without losing the legacy table.
        store = TelemetryStore(db)
        cols = {row[1] for row in store._conn.execute("PRAGMA table_info(task_records)")}
        assert "est_usd" in cols
        store.record_task(_task_record(usd=0.1, est_usd=0.2))
        loaded = store.get_task("sess-1")
        assert loaded is not None and loaded.est_usd == pytest.approx(0.2)
        store.close()

    @pytest.mark.unit
    def test_est_usd_round_trips(self, store: TelemetryStore) -> None:
        store.record_task(_task_record(usd=0.12, est_usd=0.24))
        loaded = store.get_task("sess-1")
        assert loaded is not None
        assert loaded.usd == pytest.approx(0.12)
        assert loaded.est_usd == pytest.approx(0.24)

    @pytest.mark.unit
    def test_calibration_defaults_to_one_when_sparse(self, store: TelemetryStore) -> None:
        store.record_task(_task_record(id="a", usd=0.10, est_usd=0.20))
        # Only one calibrated sample: below min, so stay conservative at 1.0.
        assert store.estimate_calibration() == pytest.approx(1.0)

    @pytest.mark.unit
    def test_calibration_is_median_billed_over_estimate(self, store: TelemetryStore) -> None:
        for i, (usd, est) in enumerate([(0.10, 0.20), (0.15, 0.30), (0.30, 0.30)]):
            store.record_task(_task_record(id=f"c{i}", usd=usd, est_usd=est))
        # ratios: 0.5, 0.5, 1.0 -> median 0.5
        assert store.estimate_calibration() == pytest.approx(0.5)

    @pytest.mark.unit
    def test_calibration_ignores_failed_and_incomplete(self, store: TelemetryStore) -> None:
        store.record_task(_task_record(id="ok1", usd=0.10, est_usd=0.20))
        store.record_task(_task_record(id="ok2", usd=0.10, est_usd=0.20))
        store.record_task(_task_record(id="ok3", usd=0.10, est_usd=0.20))
        store.record_task(_task_record(id="fail", outcome="error", usd=9.0, est_usd=0.01))
        store.record_task(_task_record(id="noest", usd=0.5, est_usd=None))
        assert store.estimate_calibration() == pytest.approx(0.5)

    @pytest.mark.unit
    def test_records_are_sanitized(self, store: TelemetryStore) -> None:
        store.record_task(
            _task_record(outcome="failed: ssh nvidia@192.168.1.44 with key /home/jo/.ssh/orin")
        )
        loaded = store.get_task("sess-1")
        assert loaded is not None
        assert "192.168.1.44" not in loaded.outcome
        assert "/home/jo" not in loaded.outcome
        assert "[REDACTED-IP]" in loaded.outcome

    @pytest.mark.unit
    def test_failure_events_and_candidates(self, store: TelemetryStore) -> None:
        store.record_failure(
            FailureEvent(
                session_id="sess-2",
                ts=time.time(),
                tool_name="Bash",
                error="pytest failed: 3 tests",
                failure_tag="unit_test",
            )
        )
        failures = store.failures_for_session("sess-2")
        assert len(failures) == 1
        assert failures[0].failure_tag == "unit_test"
        assert store.failures_for_session("other") == []


class TestSanitizer:
    @pytest.mark.unit
    @pytest.mark.parametrize(
        ("dirty", "must_not_contain"),
        [
            ("key sk-ant-abc123def456ghi789", "sk-ant-abc123def456"),
            ("host 10.0.0.7 unreachable", "10.0.0.7"),
            ("wrote /home/sherin/notes.txt", "/home/sherin"),
            ("wrote /Users/sherin/notes.txt", "/Users/sherin"),
            ("token=abc123secret", "abc123secret"),
            ("ghp_" + "a" * 30, "ghp_" + "a" * 30),
        ],
    )
    def test_redactions(self, dirty: str, must_not_contain: str) -> None:
        assert must_not_contain not in sanitize_text(dirty)

    @pytest.mark.unit
    def test_clean_text_untouched(self) -> None:
        text = "quantized yolo to INT8 in 4 loops on the jp6 container"
        assert sanitize_text(text) == text


class TestTaxonomy:
    @pytest.mark.unit
    @pytest.mark.parametrize(
        ("tool", "error", "expected"),
        [
            ("Bash", "ssh: connect to host: Connection refused", "deploy_ssh"),
            ("Bash", "clang-tidy found 3 issues", "static_analysis"),
            ("Bash", "pytest: 2 failed, 1 passed", "unit_test"),
            ("Bash", "ModuleNotFoundError: No module named 'foo'", "build_deps"),
            ("Bash", "nvcc fatal: unsupported gpu architecture", "build_toolchain"),
            ("Bash", "Segmentation fault (core dumped)", "runtime_crash"),
            ("Bash", "GPU thermal throttling engaged", "thermal"),
            ("Read", "file has no vowels", None),
        ],
    )
    def test_classification(self, tool: str, error: str, expected: str | None) -> None:
        tag = classify_failure(tool, error)
        assert tag == expected
        if tag is not None:
            assert tag in FAILURE_TAGS


def _failure_input(session: str, error: str, interrupt: bool = False) -> dict[str, Any]:
    return {
        "session_id": session,
        "transcript_path": "/tmp/t",
        "cwd": str(REPO_ROOT),
        "permission_mode": "default",
        "agent_id": "a",
        "agent_type": "implementer",
        "hook_event_name": "PostToolUseFailure",
        "tool_name": "Bash",
        "tool_input": {"command": "x"},
        "tool_use_id": "toolu-1",
        "error": error,
        "is_interrupt": interrupt,
    }


def _stop_input(session: str) -> dict[str, Any]:
    return {
        "session_id": session,
        "transcript_path": "/tmp/t",
        "cwd": str(REPO_ROOT),
        "permission_mode": "default",
        "hook_event_name": "Stop",
        "stop_hook_active": False,
    }


class TestTelemetryTap:
    @pytest.mark.unit
    def test_failure_recorded_and_classified(
        self, store: TelemetryStore, hook_context: HookContext
    ) -> None:
        tap = make_telemetry_tap(store, board="agx-orin")
        asyncio.run(tap(_failure_input("sess-3", "pytest: 1 failed"), None, hook_context))
        failures = store.failures_for_session("sess-3")
        assert failures[0].failure_tag == "unit_test"

    @pytest.mark.unit
    def test_interrupts_not_recorded(
        self, store: TelemetryStore, hook_context: HookContext
    ) -> None:
        tap = make_telemetry_tap(store)
        asyncio.run(tap(_failure_input("sess-4", "user hit esc", True), None, hook_context))
        assert store.failures_for_session("sess-4") == []

    @pytest.mark.unit
    def test_failed_then_stopped_drafts_candidate(
        self, store: TelemetryStore, hook_context: HookContext
    ) -> None:
        tap = make_telemetry_tap(store, board="agx-orin")
        asyncio.run(
            tap(
                _failure_input("sess-5", "nvcc fatal: bad arch at 10.0.0.9"),
                None,
                hook_context,
            )
        )
        asyncio.run(tap(_stop_input("sess-5"), None, hook_context))
        candidates = store.corpus_candidates(approved=False)
        assert len(candidates) == 1
        assert candidates[0].hw_config == "agx-orin"
        assert "10.0.0.9" not in candidates[0].symptom
        assert "jetson" in candidates[0].versions

    @pytest.mark.unit
    def test_clean_session_drafts_nothing(
        self, store: TelemetryStore, hook_context: HookContext
    ) -> None:
        tap = make_telemetry_tap(store)
        asyncio.run(tap(_stop_input("sess-6"), None, hook_context))
        assert store.corpus_candidates() == []
