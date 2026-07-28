---
name: cuda-kernel-optimization
description: coalescing, occupancy, streams. DRAFT methodology pack, unreviewed, no paired golden.
tier: T2
status: draft-unreviewed
---

# cuda-kernel-optimization (draft, unreviewed)

> Status: DRAFT. Not owner-reviewed and has no paired golden, so it does
> not yet meet the Part A3 skill contract. Methodology only: every
> device-specific value below is deliberately deferred to retrieval or
> on-hardware measurement, never asserted from memory (CLAUDE.md s1, s23).

Scope: coalescing, occupancy, streams.

## Methodology and traps

- Profile before optimizing: nsight tells you if the kernel is memory-bound or compute-bound, and the fix differs entirely.
- Coalesced global-memory access and occupancy usually beat clever arithmetic; check the memory pattern first.
- Overlap copy and compute with streams only after the kernel itself is efficient; premature streaming hides nothing.
- Verify correctness against a reference after every optimization; fast and wrong is worse than slow and right.

## Retrieve or verify (do not assume)

- the target GPU's compute capability and resource limits (from nvidia-smi / the arch spec).

## Before this becomes a real skill

- Pair it with a golden that fails or exceeds loop budget without it.
- Replace each 'retrieve or verify' item with a provenance-carried fact.
- Owner line-by-line review.
