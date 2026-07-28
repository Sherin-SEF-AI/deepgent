---
name: fleet-deployment
description: OTA, staged rollout, rollback criteria. DRAFT methodology pack, unreviewed, no paired golden.
tier: T2
status: draft-unreviewed
---

# fleet-deployment (draft, unreviewed)

> Status: DRAFT. Not owner-reviewed and has no paired golden, so it does
> not yet meet the Part A3 skill contract. Methodology only: every
> device-specific value below is deliberately deferred to retrieval or
> on-hardware measurement, never asserted from memory (CLAUDE.md s1, s23).

Scope: OTA, staged rollout, rollback criteria.

## Methodology and traps

- Stage every rollout (canary, then cohort, then fleet) with explicit rollback criteria defined before the rollout, not during an incident.
- A rollout needs health signals to gate on; deploying without observability is deploying blind.
- Version and pin what each cohort runs so a regression is attributable to a specific change.

## Retrieve or verify (do not assume)

- the fleet's cohort structure and health metrics.

## Before this becomes a real skill

- Pair it with a golden that fails or exceeds loop budget without it.
- Replace each 'retrieve or verify' item with a provenance-carried fact.
- Owner line-by-line review.
