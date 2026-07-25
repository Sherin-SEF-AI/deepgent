# Running the knowledge server locally

The knowledge tools (`matrix_query`, `upgrade_check`, `premortem`, `triage`,
`scaffold_driver`) query the server-side knowledge API. With no server
configured they degrade to a note; point the client at a running server and
they return real, provenance-carried answers.

## 1. Seed the matrix from versions.toml

`versions.toml` is deepgent's verified source of truth for stack versions
(CLAUDE.md section 13). Seed it into a fresh knowledge db as anchored pairwise
compatibility claims (each component verified against its L4T platform):

```
cd server
uv run python -m deepgent_server.seed --versions ../versions.toml --db knowledge.db
# seeded 9 verified matrix claim(s) into knowledge.db
```

Every claim cites `versions.toml:jetson.<line>` as its evidence; nothing is
sourced from model memory.

## 2. Run the server (authenticated)

The server never runs without a token (CLAUDE.md section 20). The matrix and
corpus live in `<db>.knowledge`, so seed that same path:

```
cd server
export DEEPGENT_SERVER_TOKEN="$(openssl rand -hex 24)"
export DEEPGENT_SERVER_DB="rag.db"                 # RAG chunk store
export DEEPGENT_SERVER_KNOWLEDGE_DB="rag.db.knowledge"   # matrix + corpus
uv run python -m deepgent_server.seed --versions ../versions.toml --db "$DEEPGENT_SERVER_KNOWLEDGE_DB"
uv run uvicorn deepgent_server.app:create_app --factory --host 127.0.0.1 --port 8811
```

## 3. Point the deepgent client at it

```
export DEEPGENT_KNOWLEDGE__API_URL="http://127.0.0.1:8811"
export DEEPGENT_KNOWLEDGE_TOKEN="<the same token>"
```

Now the client resolves real claims. Verified end to end:

- `matrix_query {l4t: 36.4.3, tensorrt: 10.3}` -> `verified_pass` with evidence
  `versions.toml:jetson.jp6`
- `upgrade_check` moving CUDA to a jp7 version on the jp6 platform -> honest
  `UNKNOWN` with the verdict "run the golden suite on the target stack before
  upgrading"
- `premortem` runs against the live corpus (empty until owner-approved failure
  tuples are added, so it reports "no prior failures" rather than "unavailable")

## What still needs real source data

- The **RAG datasheet corpus** is empty. Ingest public datasheet PDFs with
  `POST /rag/ingest` (or `deepgent rag ingest`); pin/binding questions and
  `scaffold_driver` stay unanswered until then. Public docs only (CLAUDE.md
  section 1); never ingest DeepMost-derived material.
- The **failure corpus** fills from owner-approved telemetry tuples
  (`POST /corpus/tuples`), which is what `premortem`/`triage` search.
