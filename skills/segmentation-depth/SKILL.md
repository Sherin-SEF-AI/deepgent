---
name: segmentation-depth
description: semantic/instance, mono/stereo depth. DRAFT methodology pack, unreviewed, no paired golden.
tier: T2
status: draft-unreviewed
---

# segmentation-depth (draft, unreviewed)

> Status: DRAFT. Not owner-reviewed and has no paired golden, so it does
> not yet meet the Part A3 skill contract. Methodology only: every
> device-specific value below is deliberately deferred to retrieval or
> on-hardware measurement, never asserted from memory (CLAUDE.md s1, s23).

Scope: semantic/instance, mono/stereo depth.

## Methodology and traps

- Semantic vs instance vs panoptic change both the head and the metric; fix the task before choosing a model.
- Stereo depth quality is bounded by baseline, calibration, and texture; measure error vs range, not a single number.
- Mono depth is scale-ambiguous without a metric cue; know whether downstream needs metric or relative depth.

## Retrieve or verify (do not assume)

- the depth accuracy requirement vs range for the use case.
- the calibration quality of the stereo rig if used.

## Before this becomes a real skill

- Pair it with a golden that fails or exceeds loop budget without it.
- Replace each 'retrieve or verify' item with a provenance-carried fact.
- Owner line-by-line review.
