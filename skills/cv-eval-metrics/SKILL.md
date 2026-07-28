---
name: cv-eval-metrics
description: mAP variants, HOTA/MOTA, calibration curves. DRAFT methodology pack, unreviewed, no paired golden.
tier: T1
status: draft-unreviewed
---

# cv-eval-metrics (draft, unreviewed)

> Status: DRAFT. Not owner-reviewed and has no paired golden, so it does
> not yet meet the Part A3 skill contract. Methodology only: every
> device-specific value below is deliberately deferred to retrieval or
> on-hardware measurement, never asserted from memory (CLAUDE.md s1, s23).

Scope: mAP variants, HOTA/MOTA, calibration curves.

## Methodology and traps

- State the exact mAP variant (IoU thresholds, area ranges, per-class averaging); numbers are not comparable across variants.
- Calibration matters for downstream fusion; a high-accuracy model with bad confidence calibration misleads a tracker or planner.
- Report on the deployment distribution; a dataset-average metric hides night/rain failure.

## Retrieve or verify (do not assume)

- the metric definition and evaluation split that stakeholders agreed on.

## Before this becomes a real skill

- Pair it with a golden that fails or exceeds loop budget without it.
- Replace each 'retrieve or verify' item with a provenance-carried fact.
- Owner line-by-line review.
