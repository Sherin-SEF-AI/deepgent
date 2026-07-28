---
name: bev-occupancy
description: LSS/BEVFormer family, multi-cam to BEV. DRAFT methodology pack, unreviewed, no paired golden.
tier: T2
status: draft-unreviewed
---

# bev-occupancy (draft, unreviewed)

> Status: DRAFT. Not owner-reviewed and has no paired golden, so it does
> not yet meet the Part A3 skill contract. Methodology only: every
> device-specific value below is deliberately deferred to retrieval or
> on-hardware measurement, never asserted from memory (CLAUDE.md s1, s23).

Scope: LSS/BEVFormer family, multi-cam to BEV.

## Methodology and traps

- Multi-camera-to-BEV depends on accurate extrinsics; small calibration error smears the BEV grid.
- LSS-style lifting and transformer-style attention trade compute for accuracy differently; pick for the device budget.
- Temporal fusion improves occupancy but needs consistent ego-motion; verify pose quality first.

## Retrieve or verify (do not assume)

- the camera rig extrinsics/intrinsics quality.
- the BEV grid resolution and range the task needs.

## Before this becomes a real skill

- Pair it with a golden that fails or exceeds loop budget without it.
- Replace each 'retrieve or verify' item with a provenance-carried fact.
- Owner line-by-line review.
