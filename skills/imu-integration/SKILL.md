---
name: imu-integration
description: Allan variance, bias, thermal drift. DRAFT methodology pack, unreviewed, no paired golden.
tier: T1
status: draft-unreviewed
---

# imu-integration (draft, unreviewed)

> Status: DRAFT. Not owner-reviewed and has no paired golden, so it does
> not yet meet the Part A3 skill contract. Methodology only: every
> device-specific value below is deliberately deferred to retrieval or
> on-hardware measurement, never asserted from memory (CLAUDE.md s1, s23).

Scope: Allan variance, bias, thermal drift.

## Methodology and traps

- Characterize noise with an Allan-variance plot from a long static log; use it to set process-noise, do not guess.
- Bias drifts with temperature; log temperature and model bias-vs-temp rather than calibrating once at room temp.
- Axis convention and units differ per device; verify sign and frame with a known rotation before fusion.

## Retrieve or verify (do not assume)

- the IMU's noise-density and bias-stability specs (datasheet, confirmed by Allan variance).
- the device axis convention and full-scale ranges.

## Before this becomes a real skill

- Pair it with a golden that fails or exceeds loop budget without it.
- Replace each 'retrieve or verify' item with a provenance-carried fact.
- Owner line-by-line review.
