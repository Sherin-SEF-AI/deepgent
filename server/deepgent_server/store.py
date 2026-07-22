"""Datasheet chunk store: sqlite FTS5 lexical index with provenance.

Deterministic v0 retrieval (BM25 via FTS5); embedding-based retrieval can
replace the ranking later without changing the API. Every chunk carries the
provenance fields fact_guard requires: doc, section, version_range, chip,
hash.
"""

import hashlib
import re
import sqlite3
import threading
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

_SCHEMA = """
CREATE TABLE IF NOT EXISTS chunks (
    id TEXT PRIMARY KEY,
    doc TEXT NOT NULL,
    section TEXT NOT NULL,
    chip TEXT NOT NULL,
    version_range TEXT NOT NULL,
    hash TEXT NOT NULL,
    text TEXT NOT NULL
);
CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
    text, content='chunks', content_rowid='rowid'
);
CREATE TRIGGER IF NOT EXISTS chunks_ai AFTER INSERT ON chunks BEGIN
    INSERT INTO chunks_fts(rowid, text) VALUES (new.rowid, new.text);
END;
"""


@dataclass(frozen=True)
class Chunk:
    """One retrievable datasheet chunk with provenance."""

    id: str
    doc: str
    section: str
    chip: str
    version_range: str
    hash: str
    text: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _fts_query(query: str) -> str:
    """Sanitize free text into an FTS5 OR-query; empty when no tokens."""
    tokens = re.findall(r"[A-Za-z0-9_]+", query)
    return " OR ".join(f'"{token}"' for token in tokens)


class ChunkStore:
    """sqlite-backed chunk storage and BM25 search."""

    def __init__(self, db_path: Path | str) -> None:
        # FastAPI serves sync endpoints from a threadpool; a single guarded
        # connection keeps sqlite access serialized and thread-legal.
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._lock = threading.Lock()
        self._conn.executescript(_SCHEMA)

    def close(self) -> None:
        self._conn.close()

    def add_chunk(
        self, *, doc: str, section: str, chip: str, version_range: str, text: str
    ) -> Chunk:
        digest = hashlib.sha256(f"{doc}\x00{section}\x00{text}".encode()).hexdigest()
        chunk = Chunk(
            id=f"ch-{digest[:16]}",
            doc=doc,
            section=section,
            chip=chip,
            version_range=version_range,
            hash=digest,
            text=text,
        )
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO chunks "
                "(id, doc, section, chip, version_range, hash, text) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    chunk.id,
                    chunk.doc,
                    chunk.section,
                    chunk.chip,
                    chunk.version_range,
                    chunk.hash,
                    chunk.text,
                ),
            )
            self._conn.commit()
        return chunk

    def get_chunk(self, chunk_id: str) -> Chunk | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT id, doc, section, chip, version_range, hash, text FROM chunks WHERE id = ?",
                (chunk_id,),
            ).fetchone()
        return Chunk(*row) if row else None

    def search(
        self, query: str, chip: str | None = None, limit: int = 8
    ) -> list[tuple[Chunk, float]]:
        """BM25-ranked chunks (lower rank score = better; negated for API)."""
        fts = _fts_query(query)
        if not fts:
            return []
        sql = (
            "SELECT c.id, c.doc, c.section, c.chip, c.version_range, c.hash, "
            "c.text, bm25(chunks_fts) AS rank "
            "FROM chunks_fts JOIN chunks c ON c.rowid = chunks_fts.rowid "
            "WHERE chunks_fts MATCH ?"
        )
        params: list[Any] = [fts]
        if chip:
            sql += " AND c.chip = ?"
            params.append(chip)
        sql += " ORDER BY rank LIMIT ?"
        params.append(limit)
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        return [(Chunk(*row[:7]), -float(row[7])) for row in rows]

    def count(self) -> int:
        with self._lock:
            row = self._conn.execute("SELECT COUNT(*) FROM chunks").fetchone()
        return int(row[0])
