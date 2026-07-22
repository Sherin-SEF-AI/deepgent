# MCP servers

Migrated from CLAUDE.md section 12 after Phase 0.

- board-farm (local, Phase 2): tools `list_boards`, `lease`, `release`,
  `deploy`, `exec`, `capture_metrics`, `power`. Board registry in
  `~/.deepgent/boards.toml`. All destructive tools tagged for safety_gate.
- datasheet-rag (server, Phase 3): tools `search(query, chip?, l4t?)`,
  `get_chunk(id)`. Returns chunks with {doc, section, version, chip, hash}.
  Ingestion pipeline (server side): table-aware PDF extraction, chunk by
  section/register block, metadata: chip, silicon rev, doc version, applicable
  L4T/JetPack range. Errata ingested separately with elevated retrieval weight.
- knowledge-matrix (server, Phase 4): `query_claim(stack...)` ->
  {status: verified_pass|verified_fail|unknown, evidence_run_id, verified_at,
  versions}. Claims are only written by the eval/verification pipeline, never by
  the model directly.
- failure-corpus (server, Phase 4): `search_symptom(text, hw, versions)` ->
  ranked tuples {symptom, hw_config, version_matrix, root_cause, fix,
  verification_run_id}.
- artifact-store (local first): content-addressed storage of engines, wheels,
  images, reports under `.deepgent/runs/`.
- carla-sim (Phase 5): scenario run + metrics for AV behavior tasks.
