---
name: automotive-ethernet
description: 100BASE-T1, SOME/IP, TSN/AVB. DRAFT methodology pack, unreviewed, no paired golden.
tier: T3
status: draft-unreviewed
---

# automotive-ethernet (draft, unreviewed)

> Status: DRAFT. Not owner-reviewed and has no paired golden, so it does
> not yet meet the Part A3 skill contract. Methodology only: every
> device-specific value below is deliberately deferred to retrieval or
> on-hardware measurement, never asserted from memory (CLAUDE.md s1, s23).

Scope: 100BASE-T1, SOME/IP, TSN/AVB.

## Methodology and traps

- 100BASE-T1 is a single twisted pair with master/slave PHY roles; both ends must agree on role or the link never comes up.
- SOME/IP service discovery and TSN scheduling are separate concerns; a service can be discoverable yet miss its TSN window.
- AVB/TSN needs every switch in the path to honor the schedule; one non-TSN hop breaks determinism.

## Retrieve or verify (do not assume)

- the PHY master/slave assignment and link config for each link.
- the SOME/IP service catalog and TSN stream reservations.

## Before this becomes a real skill

- Pair it with a golden that fails or exceeds loop budget without it.
- Replace each 'retrieve or verify' item with a provenance-carried fact.
- Owner line-by-line review.
