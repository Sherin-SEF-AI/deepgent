---
name: multi-object-tracking
description: ByteTrack/BoT-SORT, ReID, association tuning. DRAFT methodology pack, unreviewed, no paired golden.
tier: T1
status: draft-unreviewed
---

# multi-object-tracking (draft, unreviewed)

> Status: DRAFT. Not owner-reviewed and has no paired golden, so it does
> not yet meet the Part A3 skill contract. Methodology only: every
> device-specific value below is deliberately deferred to retrieval or
> on-hardware measurement, never asserted from memory (CLAUDE.md s1, s23).

Scope: ByteTrack/BoT-SORT, ReID, association tuning.

## Methodology and traps

- Association tuning (IoU/appearance thresholds) dominates MOTA/IDF1; a good detector with bad association tracks poorly.
- ReID embeddings help through occlusion but add latency and can cause ID swaps under domain shift; measure the tradeoff.
- Evaluate with HOTA in addition to MOTA; MOTA hides association quality.

## Retrieve or verify (do not assume)

- the tracking metric target (HOTA/MOTA/IDF1) for the use case.
- the frame rate and expected object density at deployment.

## Before this becomes a real skill

- Pair it with a golden that fails or exceeds loop budget without it.
- Replace each 'retrieve or verify' item with a provenance-carried fact.
- Owner line-by-line review.
