---
name: planning-control
description: MPC, pure pursuit, Stanley, lateral/longitudinal. DRAFT methodology pack, unreviewed, no paired golden.
tier: T2
status: draft-unreviewed
---

# planning-control (draft, unreviewed)

> Status: DRAFT. Not owner-reviewed and has no paired golden, so it does
> not yet meet the Part A3 skill contract. Methodology only: every
> device-specific value below is deliberately deferred to retrieval or
> on-hardware measurement, never asserted from memory (CLAUDE.md s1, s23).

Scope: MPC, pure pursuit, Stanley, lateral/longitudinal.

## Methodology and traps

- Lateral and longitudinal control decouple at low speed but couple at high speed; validate across the speed range.
- Pure pursuit and Stanley have known failure modes (cutting corners, oscillation); pick per speed/geometry and tune the lookahead.
- MPC is only as good as its model and constraints; an infeasible constraint set silently degrades to no control.

## Retrieve or verify (do not assume)

- the vehicle model parameters (wheelbase, actuation limits).
- the actuation and safety limits from the vehicle interface.

## Before this becomes a real skill

- Pair it with a golden that fails or exceeds loop budget without it.
- Replace each 'retrieve or verify' item with a provenance-carried fact.
- Owner line-by-line review.
