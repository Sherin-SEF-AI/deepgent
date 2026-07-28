---
name: memory-debugging
description: ASAN/valgrind on edge, leak hunting. DRAFT methodology pack, unreviewed, no paired golden.
tier: T1
status: draft-unreviewed
---

# memory-debugging (draft, unreviewed)

> Status: DRAFT. Not owner-reviewed and has no paired golden, so it does
> not yet meet the Part A3 skill contract. Methodology only: every
> device-specific value below is deliberately deferred to retrieval or
> on-hardware measurement, never asserted from memory (CLAUDE.md s1, s23).

Scope: ASAN/valgrind on edge, leak hunting.

## Methodology and traps

- ASAN catches most heap/stack errors cheaply; run it in CI on the x86 build before chasing bugs on the edge device.
- Valgrind is slow but finds uninitialized-read and leak bugs ASAN can miss; use both.
- On edge, a slow leak shows as an OOM after hours; trend RSS over a soak, do not sample once.

## Retrieve or verify (do not assume)

- the target's memory ceiling for OOM-threshold reasoning.

## Before this becomes a real skill

- Pair it with a golden that fails or exceeds loop budget without it.
- Replace each 'retrieve or verify' item with a provenance-carried fact.
- Owner line-by-line review.
