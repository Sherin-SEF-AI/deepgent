---
name: deepstream-pipelines
description: nvinfer, tracker, tiler, zero-copy rules. DRAFT methodology pack, unreviewed, no paired golden.
tier: T1
status: draft-unreviewed
---

# deepstream-pipelines (draft, unreviewed)

> Status: DRAFT. Not owner-reviewed and has no paired golden, so it does
> not yet meet the Part A3 skill contract. Methodology only: every
> device-specific value below is deliberately deferred to retrieval or
> on-hardware measurement, never asserted from memory (CLAUDE.md s1, s23).

Scope: nvinfer, tracker, tiler, zero-copy rules.

## Methodology and traps

- Keep buffers on the GPU (NvBufSurface) through nvinfer/tracker/tiler; one nvvideoconvert to CPU erases the pipeline's advantage.
- nvinfer config (batch, precision, network mode) must match the engine it loads; a mismatch runs but mis-detects.
- The tracker's config and the detector's class set must agree; silent ID/class drift comes from a stale tracker config.
- Probe pad buffers to measure per-element latency instead of guessing where the pipeline stalls.

## Retrieve or verify (do not assume)

- the nvinfer/tracker config schema for the DeepStream version in use.

## Before this becomes a real skill

- Pair it with a golden that fails or exceeds loop budget without it.
- Replace each 'retrieve or verify' item with a provenance-carried fact.
- Owner line-by-line review.
