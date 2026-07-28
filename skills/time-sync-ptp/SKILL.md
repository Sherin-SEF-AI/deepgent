---
name: time-sync-ptp
description: gPTP, chrony, hardware timestamping. DRAFT methodology pack, unreviewed, no paired golden.
tier: T1
status: draft-unreviewed
---

# time-sync-ptp (draft, unreviewed)

> Status: DRAFT. Not owner-reviewed and has no paired golden, so it does
> not yet meet the Part A3 skill contract. Methodology only: every
> device-specific value below is deliberately deferred to retrieval or
> on-hardware measurement, never asserted from memory (CLAUDE.md s1, s23).

Scope: gPTP, chrony, hardware timestamping.

## Methodology and traps

- gPTP needs hardware timestamping end to end; one software-timestamped hop caps the whole domain's accuracy.
- chrony/PTP interaction can fight over the clock; pick one discipline path and disable the other.
- Verify offset with a second independent reference; a locked PTP status does not prove correct time.

## Retrieve or verify (do not assume)

- which NICs/switches in the path support hardware timestamping.
- the platform's PTP hardware-clock and driver support.

## Before this becomes a real skill

- Pair it with a golden that fails or exceeds loop budget without it.
- Replace each 'retrieve or verify' item with a provenance-carried fact.
- Owner line-by-line review.
