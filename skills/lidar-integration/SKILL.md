---
name: lidar-integration
description: packet parsing, motion distortion. DRAFT methodology pack, unreviewed, no paired golden.
tier: T1
status: draft-unreviewed
---

# lidar-integration (draft, unreviewed)

> Status: DRAFT. Not owner-reviewed and has no paired golden, so it does
> not yet meet the Part A3 skill contract. Methodology only: every
> device-specific value below is deliberately deferred to retrieval or
> on-hardware measurement, never asserted from memory (CLAUDE.md s1, s23).

Scope: packet parsing, motion distortion.

## Methodology and traps

- Parse packets from the vendor spec, not a sample capture; field order and scaling differ across firmware.
- Motion distortion (skew) is real at vehicle speed: deskew points against ego-motion using per-point timestamps before fusion.
- Return-mode (strongest/last/dual) changes point semantics; fix it in config and record it.

## Retrieve or verify (do not assume)

- the sensor's packet format, timestamping, and return modes (from its interface spec).
- the extrinsic calibration to the vehicle frame.

## Before this becomes a real skill

- Pair it with a golden that fails or exceeds loop budget without it.
- Replace each 'retrieve or verify' item with a provenance-carried fact.
- Owner line-by-line review.
