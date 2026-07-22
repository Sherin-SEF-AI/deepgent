"""Compatibility matrix and failure corpus stores (docs/mcp.md).

Matrix claims are only ever written by the eval/verification pipeline,
never by a model. Corpus tuples arrive owner-approved from telemetry
candidates. Both answer queries; unknown is a first-class answer.
"""

import json
import re
import sqlite3
import threading
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

_SCHEMA = """
CREATE TABLE IF NOT EXISTS matrix_claims (
    id TEXT PRIMARY KEY,
    stack TEXT NOT NULL,
    claim TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('verified_pass', 'verified_fail')),
    evidence_run_id TEXT NOT NULL,
    verified_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS corpus_tuples (
    id TEXT PRIMARY KEY,
    symptom TEXT NOT NULL,
    hw_config TEXT,
    versions TEXT NOT NULL,
    root_cause TEXT NOT NULL,
    fix TEXT NOT NULL,
    verification_run_id TEXT NOT NULL,
    ts REAL NOT NULL
);
CREATE VIRTUAL TABLE IF NOT EXISTS corpus_fts USING fts5(
    symptom, content='corpus_tuples', content_rowid='rowid'
);
CREATE TRIGGER IF NOT EXISTS corpus_ai AFTER INSERT ON corpus_tuples BEGIN
    INSERT INTO corpus_fts(rowid, symptom) VALUES (new.rowid, new.symptom);
END;
"""


@dataclass(frozen=True)
class MatrixClaim:
    """One verified compatibility claim."""

    id: str
    stack: dict[str, str]
    claim: str
    status: str
    evidence_run_id: str
    verified_at: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CorpusTuple:
    """One resolved failure with its verified fix."""

    id: str
    symptom: str
    hw_config: str | None
    versions: dict[str, Any]
    root_cause: str
    fix: str
    verification_run_id: str
    ts: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _fts_query(query: str) -> str:
    tokens = re.findall(r"[A-Za-z0-9_]+", query)
    return " OR ".join(f'"{token}"' for token in tokens)


def stack_matches(claim_stack: dict[str, str], query_stack: dict[str, str]) -> bool:
    """A claim applies when every component it names matches the query."""
    return all(query_stack.get(key) == value for key, value in claim_stack.items())


class KnowledgeStore:
    """sqlite-backed matrix claims and corpus tuples."""

    def __init__(self, db_path: Path | str) -> None:
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._lock = threading.Lock()
        self._conn.executescript(_SCHEMA)

    def add_claim(
        self, *, stack: dict[str, str], claim: str, status: str, evidence_run_id: str
    ) -> MatrixClaim:
        record = MatrixClaim(
            id=f"mc-{uuid.uuid4().hex[:12]}",
            stack=dict(sorted(stack.items())),
            claim=claim,
            status=status,
            evidence_run_id=evidence_run_id,
            verified_at=time.time(),
        )
        with self._lock:
            self._conn.execute(
                "INSERT INTO matrix_claims "
                "(id, stack, claim, status, evidence_run_id, verified_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    record.id,
                    json.dumps(record.stack),
                    record.claim,
                    record.status,
                    record.evidence_run_id,
                    record.verified_at,
                ),
            )
            self._conn.commit()
        return record

    def query_claim(self, stack: dict[str, str]) -> MatrixClaim | None:
        """Latest verified claim applying to the queried stack, or None."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, stack, claim, status, evidence_run_id, verified_at "
                "FROM matrix_claims ORDER BY verified_at DESC"
            ).fetchall()
        for row in rows:
            claim_stack = json.loads(row[1])
            if stack_matches(claim_stack, stack):
                return MatrixClaim(
                    id=row[0],
                    stack=claim_stack,
                    claim=row[2],
                    status=row[3],
                    evidence_run_id=row[4],
                    verified_at=row[5],
                )
        return None

    def claim_count(self) -> int:
        with self._lock:
            row = self._conn.execute("SELECT COUNT(*) FROM matrix_claims").fetchone()
        return int(row[0])

    def add_tuple(
        self,
        *,
        symptom: str,
        hw_config: str | None,
        versions: dict[str, Any],
        root_cause: str,
        fix: str,
        verification_run_id: str,
    ) -> CorpusTuple:
        record = CorpusTuple(
            id=f"ct-{uuid.uuid4().hex[:12]}",
            symptom=symptom,
            hw_config=hw_config,
            versions=versions,
            root_cause=root_cause,
            fix=fix,
            verification_run_id=verification_run_id,
            ts=time.time(),
        )
        with self._lock:
            self._conn.execute(
                "INSERT INTO corpus_tuples "
                "(id, symptom, hw_config, versions, root_cause, fix, "
                "verification_run_id, ts) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    record.id,
                    record.symptom,
                    record.hw_config,
                    json.dumps(record.versions),
                    record.root_cause,
                    record.fix,
                    record.verification_run_id,
                    record.ts,
                ),
            )
            self._conn.commit()
        return record

    def search_symptom(self, text: str, hw: str | None = None, limit: int = 5) -> list[CorpusTuple]:
        fts = _fts_query(text)
        if not fts:
            return []
        sql = (
            "SELECT t.id, t.symptom, t.hw_config, t.versions, t.root_cause, "
            "t.fix, t.verification_run_id, t.ts "
            "FROM corpus_fts JOIN corpus_tuples t ON t.rowid = corpus_fts.rowid "
            "WHERE corpus_fts MATCH ?"
        )
        params: list[Any] = [fts]
        if hw:
            sql += " AND t.hw_config = ?"
            params.append(hw)
        sql += " ORDER BY bm25(corpus_fts) LIMIT ?"
        params.append(limit)
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        return [
            CorpusTuple(
                id=row[0],
                symptom=row[1],
                hw_config=row[2],
                versions=json.loads(row[3]),
                root_cause=row[4],
                fix=row[5],
                verification_run_id=row[6],
                ts=row[7],
            )
            for row in rows
        ]
