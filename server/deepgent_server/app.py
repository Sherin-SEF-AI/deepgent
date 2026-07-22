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

from deepgent_server.store import ChunkStore

TOKEN_ENV = "DEEPGENT_SERVER_TOKEN"
DB_ENV = "DEEPGENT_SERVER_DB"

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

    return app
