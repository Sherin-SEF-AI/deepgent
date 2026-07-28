---
name: gstreamer-debugging
description: pad probes, caps negotiation, latency tracing. DRAFT methodology pack, unreviewed, no paired golden.
tier: T1
status: draft-unreviewed
---

# gstreamer-debugging (draft, unreviewed)

> Status: DRAFT. Not owner-reviewed and has no paired golden, so it does
> not yet meet the Part A3 skill contract. Methodology only: every
> device-specific value below is deliberately deferred to retrieval or
> on-hardware measurement, never asserted from memory (CLAUDE.md s1, s23).

Scope: pad probes, caps negotiation, latency tracing.

## Methodology and traps

- Read caps negotiation with GST_DEBUG and pad probes; most 'no data' bugs are a caps mismatch, not a dead element.
- Latency is measured with buffer PTS at pad probes, not wall clock around the loop.
- A not-linked or not-negotiated error names the exact pad; trust it and inspect that boundary first.

## Retrieve or verify (do not assume)

- the caps each element in the target pipeline actually supports.

## Before this becomes a real skill

- Pair it with a golden that fails or exceeds loop budget without it.
- Replace each 'retrieve or verify' item with a provenance-carried fact.
- Owner line-by-line review.
