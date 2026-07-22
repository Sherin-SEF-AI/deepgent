"""FastAPI knowledge API: authenticated datasheet-rag v0.

Endpoints (all bearer-authenticated, no anonymous reads):
- POST /rag/search {query, chip?, l4t?} -> ranked chunks with provenance
- GET  /rag/chunk/{chunk_id}            -> one chunk
- POST /rag/ingest {doc, chip, version_range, section?, text} (owner mode)
- GET  /healthz                          -> liveness (auth required too)
"""

import os
import secrets
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from deepgent_server.knowledge import KnowledgeStore
from deepgent_server.store import ChunkStore

TOKEN_ENV = "DEEPGENT_SERVER_TOKEN"
DB_ENV = "DEEPGENT_SERVER_DB"
KNOWLEDGE_DB_ENV = "DEEPGENT_SERVER_KNOWLEDGE_DB"

_bearer = HTTPBearer(auto_error=False)


class SearchRequest(BaseModel):
    query: str = Field(min_length=1)
    chip: str | None = None
    l4t: str | None = None
    limit: int = Field(default=8, ge=1, le=25)


class IngestRequest(BaseModel):
    doc: str = Field(min_length=1)
    chip: str = Field(min_length=1)
    version_range: str = Field(min_length=1)
    section: str = "body"
    text: str = Field(min_length=1)


class MatrixQueryRequest(BaseModel):
    stack: dict[str, str] = Field(min_length=1)


class MatrixClaimRequest(BaseModel):
    stack: dict[str, str] = Field(min_length=1)
    claim: str = Field(min_length=1)
    status: str = Field(pattern="^(verified_pass|verified_fail)$")
    evidence_run_id: str = Field(min_length=1)


class CorpusSearchRequest(BaseModel):
    text: str = Field(min_length=1)
    hw: str | None = None
    limit: int = Field(default=5, ge=1, le=20)


class CorpusTupleRequest(BaseModel):
    symptom: str = Field(min_length=1)
    hw_config: str | None = None
    versions: dict[str, Any] = Field(default_factory=dict)
    root_cause: str = Field(min_length=1)
    fix: str = Field(min_length=1)
    verification_run_id: str = Field(min_length=1)


def create_app(db_path: Path | str | None = None, token: str | None = None) -> FastAPI:
    """Build the app. Token and DB default from the environment."""
    resolved_token = token if token is not None else os.environ.get(TOKEN_ENV, "")
    if not resolved_token:
        raise RuntimeError(
            f"{TOKEN_ENV} is not set; the knowledge server never runs "
            "without authentication (CLAUDE.md section 20)"
        )
    resolved_db = db_path if db_path is not None else os.environ.get(DB_ENV, "rag.db")
    store = ChunkStore(resolved_db)
    knowledge_db = os.environ.get(KNOWLEDGE_DB_ENV, f"{resolved_db}.knowledge")
    knowledge = KnowledgeStore(knowledge_db)
    app = FastAPI(title="deepgent knowledge API", version="0.1.0")

    def authed(
        credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    ) -> None:
        if credentials is None or not secrets.compare_digest(
            credentials.credentials, resolved_token
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="valid bearer token required",
            )

    @app.get("/healthz")
    def healthz(_: Annotated[None, Depends(authed)]) -> dict[str, Any]:
        return {"status": "ok", "chunks": store.count()}

    @app.post("/rag/search")
    def search(request: SearchRequest, _: Annotated[None, Depends(authed)]) -> dict[str, Any]:
        results = store.search(request.query, chip=request.chip, limit=request.limit)
        return {"chunks": [{**chunk.to_dict(), "score": score} for chunk, score in results]}

    @app.get("/rag/chunk/{chunk_id}")
    def get_chunk(chunk_id: str, _: Annotated[None, Depends(authed)]) -> dict[str, Any]:
        chunk = store.get_chunk(chunk_id)
        if chunk is None:
            raise HTTPException(status_code=404, detail=f"chunk {chunk_id} not found")
        return chunk.to_dict()

    @app.post("/rag/ingest")
    def ingest(request: IngestRequest, _: Annotated[None, Depends(authed)]) -> dict[str, Any]:
        chunk = store.add_chunk(
            doc=request.doc,
            section=request.section,
            chip=request.chip,
            version_range=request.version_range,
            text=request.text,
        )
        return {"id": chunk.id, "hash": chunk.hash}

    @app.post("/matrix/query")
    def matrix_query(
        request: MatrixQueryRequest, _: Annotated[None, Depends(authed)]
    ) -> dict[str, Any]:
        claim = knowledge.query_claim(request.stack)
        if claim is None:
            return {"status": "unknown"}
        return claim.to_dict()

    @app.post("/matrix/claims")
    def matrix_add(
        request: MatrixClaimRequest, _: Annotated[None, Depends(authed)]
    ) -> dict[str, Any]:
        # Written only by the eval/verification pipeline (docs/mcp.md);
        # every write must carry its evidence run.
        claim = knowledge.add_claim(
            stack=request.stack,
            claim=request.claim,
            status=request.status,
            evidence_run_id=request.evidence_run_id,
        )
        return {"id": claim.id, "verified_at": claim.verified_at}

    @app.post("/corpus/search")
    def corpus_search(
        request: CorpusSearchRequest, _: Annotated[None, Depends(authed)]
    ) -> dict[str, Any]:
        tuples = knowledge.search_symptom(request.text, hw=request.hw, limit=request.limit)
        return {"tuples": [record.to_dict() for record in tuples]}

    @app.post("/corpus/tuples")
    def corpus_add(
        request: CorpusTupleRequest, _: Annotated[None, Depends(authed)]
    ) -> dict[str, Any]:
        record = knowledge.add_tuple(
            symptom=request.symptom,
            hw_config=request.hw_config,
            versions=request.versions,
            root_cause=request.root_cause,
            fix=request.fix,
            verification_run_id=request.verification_run_id,
        )
        return {"id": record.id}

    return app
