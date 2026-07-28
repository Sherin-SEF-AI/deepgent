---
name: calibration-extrinsics
description: cam-lidar, cam-imu, targetless. DRAFT methodology pack, unreviewed, no paired golden.
tier: T1
status: draft-unreviewed
---

# calibration-extrinsics (draft, unreviewed)

> Status: DRAFT. Not owner-reviewed and has no paired golden, so it does
> not yet meet the Part A3 skill contract. Methodology only: every
> device-specific value below is deliberately deferred to retrieval or
> on-hardware measurement, never asserted from memory (CLAUDE.md s1, s23).

Scope: cam-lidar, cam-imu, targetless.

## Methodology and traps

- Extrinsic error propagates into every fusion product; treat calibration as a measured, versioned artifact, not a one-time step.
- Targetless methods are convenient but need motion excitation and good time sync; verify against a target-based result once.
- Re-calibrate after any mechanical change; a bumped sensor invalidates prior extrinsics silently.

## Retrieve or verify (do not assume)

- the sensor mounting geometry and the calibration procedure used.
- a validation metric for the resulting extrinsics.

## Before this becomes a real skill

- Pair it with a golden that fails or exceeds loop budget without it.
- Replace each 'retrieve or verify' item with a provenance-carried fact.
- Owner line-by-line review.
