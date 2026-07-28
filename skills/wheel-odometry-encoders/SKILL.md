---
name: wheel-odometry-encoders
description: wheel odometry and encoders. DRAFT methodology pack, unreviewed, no paired golden.
tier: T2
status: draft-unreviewed
---

# wheel-odometry-encoders (draft, unreviewed)

> Status: DRAFT. Not owner-reviewed and has no paired golden, so it does
> not yet meet the Part A3 skill contract. Methodology only: every
> device-specific value below is deliberately deferred to retrieval or
> on-hardware measurement, never asserted from memory (CLAUDE.md s1, s23).

Scope: wheel odometry and encoders.

## Methodology and traps

- Odometry error is systematic (scale, wheelbase) plus random (slip); calibrate the systematic part on a measured path.
- Encoder resolution and update rate bound velocity estimate quality at low speed.
- Wheel slip and tire radius change with load and pressure; treat odometry as a prior, not truth.

## Retrieve or verify (do not assume)

- encoder counts-per-rev and the drivetrain geometry.
- the calibration path/procedure for scale and track width.

## Before this becomes a real skill

- Pair it with a golden that fails or exceeds loop budget without it.
- Replace each 'retrieve or verify' item with a provenance-carried fact.
- Owner line-by-line review.
