---
name: slam-localization
description: LIO-SAM family, map management, drift. DRAFT methodology pack, unreviewed, no paired golden.
tier: T2
status: draft-unreviewed
---

# slam-localization (draft, unreviewed)

> Status: DRAFT. Not owner-reviewed and has no paired golden, so it does
> not yet meet the Part A3 skill contract. Methodology only: every
> device-specific value below is deliberately deferred to retrieval or
> on-hardware measurement, never asserted from memory (CLAUDE.md s1, s23).

Scope: LIO-SAM family, map management, drift.

## Methodology and traps

- Drift is inevitable; the design question is loop closure and map management, not eliminating drift.
- LIO-family accuracy depends on IMU quality and extrinsic calibration; garbage extrinsics defeat a good algorithm.
- Evaluate on a trajectory with ground truth or loop closure, not by eyeballing a point cloud.

## Retrieve or verify (do not assume)

- the lidar-IMU extrinsics and IMU noise model.
- a ground-truth or loop-closure reference for evaluation.

## Before this becomes a real skill

- Pair it with a golden that fails or exceeds loop budget without it.
- Replace each 'retrieve or verify' item with a provenance-carried fact.
- Owner line-by-line review.
