---
name: radar-integration
description: mmWave config, CAN/Ethernet radar. DRAFT methodology pack, unreviewed, no paired golden.
tier: T2
status: draft-unreviewed
---

# radar-integration (draft, unreviewed)

> Status: DRAFT. Not owner-reviewed and has no paired golden, so it does
> not yet meet the Part A3 skill contract. Methodology only: every
> device-specific value below is deliberately deferred to retrieval or
> on-hardware measurement, never asserted from memory (CLAUDE.md s1, s23).

Scope: mmWave config, CAN/Ethernet radar.

## Methodology and traps

- mmWave chirp/profile config trades range, velocity, and resolution; there is no single good config, tune to the use case.
- CAN and automotive-ethernet radars deliver tracks vs point clouds differently; know which the sensor emits before writing the consumer.
- Ghost and multipath detections are expected; filtering belongs in the consumer, not assumed away.

## Retrieve or verify (do not assume)

- the radar's config interface and output format (tracks vs detections) from its manual.
- the chirp parameters valid for the required range/velocity.

## Before this becomes a real skill

- Pair it with a golden that fails or exceeds loop budget without it.
- Replace each 'retrieve or verify' item with a provenance-carried fact.
- Owner line-by-line review.
