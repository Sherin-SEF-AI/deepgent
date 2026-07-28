---
name: low-power-design
description: sleep modes, wake sources, budgets. DRAFT methodology pack, unreviewed, no paired golden.
tier: T2
status: draft-unreviewed
---

# low-power-design (draft, unreviewed)

> Status: DRAFT. Not owner-reviewed and has no paired golden, so it does
> not yet meet the Part A3 skill contract. Methodology only: every
> device-specific value below is deliberately deferred to retrieval or
> on-hardware measurement, never asserted from memory (CLAUDE.md s1, s23).

Scope: sleep modes, wake sources, budgets.

## Methodology and traps

- Measure sleep current, do not estimate it; one peripheral left enabled dominates the budget.
- Enumerate wake sources explicitly; an unexpected wake source drains the battery between real events.
- Duty cycle sets battery life more than active current; optimize how often, not just how much.

## Retrieve or verify (do not assume)

- the SoC/peripheral sleep-mode currents and wake sources (from datasheets, confirmed by measurement).

## Before this becomes a real skill

- Pair it with a golden that fails or exceeds loop budget without it.
- Replace each 'retrieve or verify' item with a provenance-carried fact.
- Owner line-by-line review.
