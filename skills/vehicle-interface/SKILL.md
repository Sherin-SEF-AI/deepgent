---
name: vehicle-interface
description: drive-by-wire, actuation limits, e-stop design. DRAFT methodology pack, unreviewed, no paired golden.
tier: T2
status: draft-unreviewed
---

# vehicle-interface (draft, unreviewed)

> Status: DRAFT. Not owner-reviewed and has no paired golden, so it does
> not yet meet the Part A3 skill contract. Methodology only: every
> device-specific value below is deliberately deferred to retrieval or
> on-hardware measurement, never asserted from memory (CLAUDE.md s1, s23).

Scope: drive-by-wire, actuation limits, e-stop design.

## Methodology and traps

- E-stop and actuation limits are safety functions; design them independent of the autonomy stack so a stack crash still stops safely.
- Drive-by-wire command rates and watchdogs are strict; a missed heartbeat must fail safe, not hold last command.
- Never bench-test actuation commands on a live vehicle without a physical isolation and abort path.

## Retrieve or verify (do not assume)

- the drive-by-wire command set, rates, and watchdog behavior (from the vehicle spec, owner-reviewed).
- the actuation limits and e-stop wiring for the platform.

## Before this becomes a real skill

- Pair it with a golden that fails or exceeds loop budget without it.
- Replace each 'retrieve or verify' item with a provenance-carried fact.
- Owner line-by-line review.
