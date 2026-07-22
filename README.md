# deepgent

Domain-locked autonomous engineering agent for autonomous vehicles, computer
vision, and embedded systems. Takes a task from natural language to a verified
artifact running on target hardware at spec. Built on the Claude Agent SDK.

Personal project of Sherin Joseph Roy (github.com/Sherin-SEF-AI). Not a
DeepMost AI product.

## Scope

AV, CV, embedded, and robotics-adjacent edge AI only. The definition of done is
that the artifact runs on target hardware and meets the stated metric (fps, p99
latency, mAP delta, memory, thermal).

## Status

Phase 0 (bootstrap). Repo scaffold, tooling, and CI only; agent logic lands in
subsequent work orders. See CLAUDE.md for the full architecture and phase plan.

## Development

Python 3.12, managed with [uv](https://docs.astral.sh/uv/):

```
uv sync
uv run ruff check
uv run mypy src/
uv run pytest -m "not hardware"
```

## License

Client/harness code is licensed under Apache-2.0. The knowledge layer (`server/`
and skill content) is proprietary and lives behind an authenticated API.
