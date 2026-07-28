---
name: camera-sync-trigger
description: hardware trigger, PTP, PPS alignment. DRAFT methodology pack, unreviewed, no paired golden.
tier: T1
status: draft-unreviewed
---

# camera-sync-trigger (draft, unreviewed)

> Status: DRAFT. Not owner-reviewed and has no paired golden, so it does
> not yet meet the Part A3 skill contract. Methodology only: every
> device-specific value below is deliberately deferred to retrieval or
> on-hardware measurement, never asserted from memory (CLAUDE.md s1, s23).

Scope: hardware trigger, PTP, PPS alignment.

## Methodology and traps

- Software timestamps are not synchronization; hardware trigger or PTP-disciplined capture is required for multi-camera fusion.
- Trigger-to-exposure latency is per-sensor and often asymmetric; characterize it rather than assuming zero.
- PPS/PTP alignment must be verified end to end (source to image timestamp), not just at the clock source.

## Retrieve or verify (do not assume)

- the sensor's external-trigger mode and trigger-to-exposure delay (datasheet / measured).
- the platform's hardware-timestamping capability for capture.

## Before this becomes a real skill

- Pair it with a golden that fails or exceeds loop budget without it.
- Replace each 'retrieve or verify' item with a provenance-carried fact.
- Owner line-by-line review.
