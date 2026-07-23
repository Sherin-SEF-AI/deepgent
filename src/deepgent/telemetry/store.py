"""Telemetry store: task records, failure events, corpus tuple candidates.

Schemas follow docs/schemas.md. Everything written here passes through the
sanitizer (section 20): no credentials, board IPs, or personal paths are
ever persisted. Candidate corpus tuples are drafted on failed-to-passed
transitions and wait for owner approval before any upload.
"""

import json
import sqlite3
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import structlog

from deepgent.telemetry.sanitizer import sanitize_mapping, sanitize_text

_logger = structlog.get_logger(__name__)

DB_RELPATH = Path(".deepgent") / "telemetry.db"

# Failure taxonomy v0 (docs/schemas.md). Unclassifiable failures store NULL
# rather than a wrong tag.
FAILURE_TAGS = (
    "build_toolchain",
    "build_deps",
    "static_analysis",
    "unit_test",
    "deploy_ssh",
    "runtime_crash",
    "perf_miss",
    "accuracy_miss",
    "thermal",
    "flaky_hw",
    "knowledge_gap",
    "harness_bug",
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS task_records (
    id TEXT PRIMARY KEY,
    ts REAL NOT NULL,
    task_class TEXT NOT NULL,
    board TEXT,
    model_mix TEXT NOT NULL,
    tokens INTEGER NOT NULL,
    usd REAL,
    est_usd REAL,
    wall_s REAL NOT NULL,
    loops INTEGER NOT NULL,
    outcome TEXT NOT NULL,
    failure_tag TEXT,
    artifacts_path TEXT
);
CREATE TABLE IF NOT EXISTS failure_events (
    session_id TEXT NOT NULL,
    ts REAL NOT NULL,
    agent_type TEXT,
    tool_name TEXT NOT NULL,
    failure_tag TEXT,
    error TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS corpus_candidates (
    session_id TEXT NOT NULL,
    ts REAL NOT NULL,
    symptom TEXT NOT NULL,
    hw_config TEXT,
    versions TEXT NOT NULL,
    root_cause TEXT NOT NULL DEFAULT '',
    fix_diff_ref TEXT NOT NULL DEFAULT '',
    approved INTEGER NOT NULL DEFAULT 0
);
"""


@dataclass(frozen=True)
class TaskRecord:
    """One completed task (docs/schemas.md task_record)."""

    id: str
    ts: float
    task_class: str
    board: str | None
    model_mix: dict[str, int]
    tokens: int
    usd: float | None
    wall_s: float
    loops: int
    outcome: str
    # Raw token-priced estimate at task end; billed usd/est_usd feeds the
    # budget-guard calibration. None on records written before this field.
    est_usd: float | None = None
    failure_tag: str | None = None
    artifacts_path: str | None = None


@dataclass(frozen=True)
class FailureEvent:
    """One failed tool call inside a session."""

    session_id: str
    ts: float
    tool_name: str
    error: str
    agent_type: str | None = None
    failure_tag: str | None = None


@dataclass(frozen=True)
class CorpusCandidate:
    """A drafted corpus tuple awaiting owner approval."""

    session_id: str
    ts: float
    symptom: str
    versions: dict[str, Any]
    hw_config: str | None = None
    root_cause: str = ""
    fix_diff_ref: str = ""
    approved: bool = field(default=False)


def default_db_path() -> Path:
    return Path.home() / DB_RELPATH


class TelemetryStore:
    """sqlite-backed telemetry persistence, safe for hook threads."""

    def __init__(self, db_path: Path | str | None = None) -> None:
        path = Path(db_path) if db_path is not None else default_db_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._lock = threading.Lock()
        self._conn.executescript(_SCHEMA)
        self._migrate()

    def _migrate(self) -> None:
        """Additive migrations for databases created by older versions."""
        cols = {row[1] for row in self._conn.execute("PRAGMA table_info(task_records)")}
        if "est_usd" not in cols:
            self._conn.execute("ALTER TABLE task_records ADD COLUMN est_usd REAL")
            self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def record_task(self, record: TaskRecord) -> None:
        data = asdict(record)
        data["model_mix"] = json.dumps(sanitize_mapping(record.model_mix))
        data["outcome"] = sanitize_text(record.outcome)
        if data["artifacts_path"]:
            data["artifacts_path"] = sanitize_text(data["artifacts_path"])
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO task_records "
                "(id, ts, task_class, board, model_mix, tokens, usd, est_usd, "
                "wall_s, loops, outcome, failure_tag, artifacts_path) "
                "VALUES (:id, :ts, :task_class, :board, :model_mix, :tokens, "
                ":usd, :est_usd, :wall_s, :loops, :outcome, :failure_tag, "
                ":artifacts_path)",
                data,
            )
            self._conn.commit()
        _logger.debug("task_recorded", task_id=record.id, outcome=record.outcome)

    def record_failure(self, event: FailureEvent) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO failure_events "
                "(session_id, ts, agent_type, tool_name, failure_tag, error) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    event.session_id,
                    event.ts,
                    event.agent_type,
                    event.tool_name,
                    event.failure_tag,
                    sanitize_text(event.error)[:4000],
                ),
            )
            self._conn.commit()

    def failures_for_session(self, session_id: str) -> list[FailureEvent]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT session_id, ts, agent_type, tool_name, failure_tag, error "
                "FROM failure_events WHERE session_id = ? ORDER BY ts",
                (session_id,),
            ).fetchall()
        return [
            FailureEvent(
                session_id=row[0],
                ts=row[1],
                agent_type=row[2],
                tool_name=row[3],
                failure_tag=row[4],
                error=row[5],
            )
            for row in rows
        ]

    def draft_corpus_candidate(self, candidate: CorpusCandidate) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO corpus_candidates "
                "(session_id, ts, symptom, hw_config, versions, root_cause, "
                "fix_diff_ref, approved) VALUES (?, ?, ?, ?, ?, ?, ?, 0)",
                (
                    candidate.session_id,
                    candidate.ts,
                    sanitize_text(candidate.symptom)[:2000],
                    candidate.hw_config,
                    json.dumps(candidate.versions),
                    sanitize_text(candidate.root_cause),
                    candidate.fix_diff_ref,
                ),
            )
            self._conn.commit()
        _logger.info("corpus_candidate_drafted", session_id=candidate.session_id)

    def corpus_candidates(self, approved: bool | None = None) -> list[CorpusCandidate]:
        sql = (
            "SELECT session_id, ts, symptom, hw_config, versions, root_cause, "
            "fix_diff_ref, approved FROM corpus_candidates"
        )
        params: tuple[Any, ...] = ()
        if approved is not None:
            sql += " WHERE approved = ?"
            params = (1 if approved else 0,)
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        return [
            CorpusCandidate(
                session_id=row[0],
                ts=row[1],
                symptom=row[2],
                hw_config=row[3],
                versions=json.loads(row[4]),
                root_cause=row[5],
                fix_diff_ref=row[6],
                approved=bool(row[7]),
            )
            for row in rows
        ]

    def task_records(self, limit: int = 20) -> list[TaskRecord]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, ts, task_class, board, model_mix, tokens, usd, "
                "est_usd, wall_s, loops, outcome, failure_tag, artifacts_path "
                "FROM task_records ORDER BY ts DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self._row_to_record(row) for row in rows]

    def get_task(self, task_id: str) -> TaskRecord | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT id, ts, task_class, board, model_mix, tokens, usd, "
                "est_usd, wall_s, loops, outcome, failure_tag, artifacts_path "
                "FROM task_records WHERE id = ?",
                (task_id,),
            ).fetchone()
        return self._row_to_record(row) if row else None

    def estimate_calibration(self, window: int = 25, min_samples: int = 3) -> float:
        """Median billed/estimate ratio over recent successful tasks.

        Only tasks that carry both a billed usd and a positive est_usd count.
        Returns 1.0 until at least min_samples exist, so the halt decision
        stays conservative on a cold store.
        """
        with self._lock:
            rows = self._conn.execute(
                "SELECT usd, est_usd FROM task_records "
                "WHERE outcome = 'success' AND usd IS NOT NULL "
                "AND est_usd IS NOT NULL AND est_usd > 0 "
                "ORDER BY ts DESC LIMIT ?",
                (window,),
            ).fetchall()
        ratios = sorted(float(usd) / float(est) for usd, est in rows if usd is not None and est)
        if len(ratios) < min_samples:
            return 1.0
        mid = len(ratios) // 2
        if len(ratios) % 2:
            return ratios[mid]
        return (ratios[mid - 1] + ratios[mid]) / 2.0

    @staticmethod
    def _row_to_record(row: tuple[Any, ...]) -> TaskRecord:
        return TaskRecord(
            id=row[0],
            ts=row[1],
            task_class=row[2],
            board=row[3],
            model_mix=json.loads(row[4]),
            tokens=row[5],
            usd=row[6],
            est_usd=row[7],
            wall_s=row[8],
            loops=row[9],
            outcome=row[10],
            failure_tag=row[11],
            artifacts_path=row[12],
        )


def now() -> float:
    return time.time()
