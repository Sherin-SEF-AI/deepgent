---
name: simulation-carla
description: scenarios, sensor models, sim2real gap. DRAFT methodology pack, unreviewed, no paired golden.
tier: T3
status: draft-unreviewed
---

# simulation-carla (draft, unreviewed)

> Status: DRAFT. Not owner-reviewed and has no paired golden, so it does
> not yet meet the Part A3 skill contract. Methodology only: every
> device-specific value below is deliberately deferred to retrieval or
> on-hardware measurement, never asserted from memory (CLAUDE.md s1, s23).

Scope: scenarios, sensor models, sim2real gap.

## Methodology and traps

- The sim2real gap is the point: use sim for scenario coverage and regression, not for absolute perception accuracy claims.
- Sensor models are approximations; a detector that passes in sim can fail on real noise and lens effects.
- Version scenarios and sensor configs so a sim regression is reproducible.

## Retrieve or verify (do not assume)

- the sensor-model fidelity vs the real sensors used.

## Before this becomes a real skill

- Pair it with a golden that fails or exceeds loop budget without it.
- Replace each 'retrieve or verify' item with a provenance-carried fact.
- Owner line-by-line review.
