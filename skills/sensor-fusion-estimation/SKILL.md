---
name: sensor-fusion-estimation
description: EKF/UKF/ESKF, robot_localization. DRAFT methodology pack, unreviewed, no paired golden.
tier: T1
status: draft-unreviewed
---

# sensor-fusion-estimation (draft, unreviewed)

> Status: DRAFT. Not owner-reviewed and has no paired golden, so it does
> not yet meet the Part A3 skill contract. Methodology only: every
> device-specific value below is deliberately deferred to retrieval or
> on-hardware measurement, never asserted from memory (CLAUDE.md s1, s23).

Scope: EKF/UKF/ESKF, robot_localization.

## Methodology and traps

- Filter tuning is process-noise vs measurement-noise; set them from measured sensor characteristics, not by trial and error.
- Time alignment across sensors dominates fusion quality; a fixed latency offset per sensor is usually needed.
- An EKF diverges silently under bad initialization or unmodeled nonlinearity; monitor innovation/NIS, not just the estimate.

## Retrieve or verify (do not assume)

- the per-sensor noise characteristics and timing offsets (measured).
- the motion model appropriate to the platform.

## Before this becomes a real skill

- Pair it with a golden that fails or exceeds loop budget without it.
- Replace each 'retrieve or verify' item with a provenance-carried fact.
- Owner line-by-line review.
