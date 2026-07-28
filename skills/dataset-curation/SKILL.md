---
name: dataset-curation
description: dedup, mining, splits, leakage prevention. DRAFT methodology pack, unreviewed, no paired golden.
tier: T1
status: draft-unreviewed
---

# dataset-curation (draft, unreviewed)

> Status: DRAFT. Not owner-reviewed and has no paired golden, so it does
> not yet meet the Part A3 skill contract. Methodology only: every
> device-specific value below is deliberately deferred to retrieval or
> on-hardware measurement, never asserted from memory (CLAUDE.md s1, s23).

Scope: dedup, mining, splits, leakage prevention.

## Methodology and traps

- Prevent leakage first: split by scene/sequence/vehicle, never by random frame, or val leaks into train.
- Dedup near-duplicates before splitting; identical frames across splits inflate metrics.
- Mine for rare cases deliberately; a dataset balanced by frame count is imbalanced by scenario.

## Retrieve or verify (do not assume)

- the correct split key (scene/drive/vehicle) for this dataset.
- the rare-scenario definitions the task cares about.

## Before this becomes a real skill

- Pair it with a golden that fails or exceeds loop budget without it.
- Replace each 'retrieve or verify' item with a provenance-carried fact.
- Owner line-by-line review.
