---
name: edge-inference-serving
description: batching, multi-stream scheduling. DRAFT methodology pack, unreviewed, no paired golden.
tier: T2
status: draft-unreviewed
---

# edge-inference-serving (draft, unreviewed)

> Status: DRAFT. Not owner-reviewed and has no paired golden, so it does
> not yet meet the Part A3 skill contract. Methodology only: every
> device-specific value below is deliberately deferred to retrieval or
> on-hardware measurement, never asserted from memory (CLAUDE.md s1, s23).

Scope: batching, multi-stream scheduling.

## Methodology and traps

- Batching trades latency for throughput; size the batch to the p99 latency budget, not peak throughput.
- Multi-stream scheduling contends for one accelerator; measure tail latency under concurrent streams, not in isolation.
- Warm the engine and pin memory; first-inference latency is not steady-state latency.

## Retrieve or verify (do not assume)

- the accelerator's concurrency model and memory limits.
- the latency budget and stream count at deployment.

## Before this becomes a real skill

- Pair it with a golden that fails or exceeds loop budget without it.
- Replace each 'retrieve or verify' item with a provenance-carried fact.
- Owner line-by-line review.
