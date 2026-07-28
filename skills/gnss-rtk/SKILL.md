---
name: gnss-rtk
description: NTRIP, fix quality, UBX/NMEA. DRAFT methodology pack, unreviewed, no paired golden.
tier: T2
status: draft-unreviewed
---

# gnss-rtk (draft, unreviewed)

> Status: DRAFT. Not owner-reviewed and has no paired golden, so it does
> not yet meet the Part A3 skill contract. Methodology only: every
> device-specific value below is deliberately deferred to retrieval or
> on-hardware measurement, never asserted from memory (CLAUDE.md s1, s23).

Scope: NTRIP, fix quality, UBX/NMEA.

## Methodology and traps

- Fix quality (float vs fixed) matters more than reported precision; gate downstream use on the fix type, not the covariance alone.
- NTRIP correction age and baseline length bound achievable accuracy; monitor correction latency.
- Parse UBX/NMEA from the receiver spec; NMEA precision is often lower than the receiver's internal solution.

## Retrieve or verify (do not assume)

- the receiver's message set and RTK config (from its protocol spec).
- the correction source (NTRIP mountpoint) and baseline for the deployment area.

## Before this becomes a real skill

- Pair it with a golden that fails or exceeds loop budget without it.
- Replace each 'retrieve or verify' item with a provenance-carried fact.
- Owner line-by-line review.
