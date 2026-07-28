---
name: training-pipelines
description: dataloaders, AMP, schedulers, reproducibility. DRAFT methodology pack, unreviewed, no paired golden.
tier: T0
status: draft-unreviewed
---

# training-pipelines (draft, unreviewed)

> Status: DRAFT. Not owner-reviewed and has no paired golden, so it does
> not yet meet the Part A3 skill contract. Methodology only: every
> device-specific value below is deliberately deferred to retrieval or
> on-hardware measurement, never asserted from memory (CLAUDE.md s1, s23).

Scope: dataloaders, AMP, schedulers, reproducibility.

## Methodology and traps

- Seed everything and log the seed, data version, and code commit; an unreproducible training run cannot be debugged or trusted.
- AMP changes numerics; validate accuracy under the same precision you deploy, not fp32.
- Dataloader throughput often caps GPU utilization; profile the input pipeline before blaming the model for slow training.
- Checkpoint and resume must restore optimizer and scheduler state, not just weights, or a resumed run diverges.

## Retrieve or verify (do not assume)

- the exact dataset version and split hashes used.
- the target accuracy metric and deployment precision.

## Before this becomes a real skill

- Pair it with a golden that fails or exceeds loop budget without it.
- Replace each 'retrieve or verify' item with a provenance-carried fact.
- Owner line-by-line review.
