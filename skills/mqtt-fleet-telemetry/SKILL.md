---
name: mqtt-fleet-telemetry
description: store-and-forward, backpressure. DRAFT methodology pack, unreviewed, no paired golden.
tier: T2
status: draft-unreviewed
---

# mqtt-fleet-telemetry (draft, unreviewed)

> Status: DRAFT. Not owner-reviewed and has no paired golden, so it does
> not yet meet the Part A3 skill contract. Methodology only: every
> device-specific value below is deliberately deferred to retrieval or
> on-hardware measurement, never asserted from memory (CLAUDE.md s1, s23).

Scope: store-and-forward, backpressure.

## Methodology and traps

- Design store-and-forward for the disconnected case first; edge links drop, and lost telemetry is the default failure.
- Backpressure must be bounded: an unbounded local queue turns a network outage into a disk-full outage.
- QoS level and clean-session choice change delivery guarantees and broker load; pick per topic, not globally.

## Retrieve or verify (do not assume)

- the broker's QoS/retention limits and auth scheme.
- the per-device bandwidth and storage budget for buffering.

## Before this becomes a real skill

- Pair it with a golden that fails or exceeds loop budget without it.
- Replace each 'retrieve or verify' item with a provenance-carried fact.
- Owner line-by-line review.
