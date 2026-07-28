---
name: automotive-uds-obd
description: UDS services, DoIP. DRAFT methodology pack, unreviewed, no paired golden.
tier: T2
status: draft-unreviewed
---

# automotive-uds-obd (draft, unreviewed)

> Status: DRAFT. Not owner-reviewed and has no paired golden, so it does
> not yet meet the Part A3 skill contract. Methodology only: every
> device-specific value below is deliberately deferred to retrieval or
> on-hardware measurement, never asserted from memory (CLAUDE.md s1, s23).

Scope: UDS services, DoIP.

## Methodology and traps

- UDS sessions and security access are stateful; a service that works in default session is rejected in a locked one.
- DoIP adds a transport and discovery layer over UDS; timeouts and routing activation are extra failure points.
- Never test destructive UDS routines (actuator, reset) on a live vehicle without an isolation plan.

## Retrieve or verify (do not assume)

- the ECU's supported UDS services and security-access scheme (from its spec).
- DoIP addressing and routing for the target ECU.

## Before this becomes a real skill

- Pair it with a golden that fails or exceeds loop budget without it.
- Replace each 'retrieve or verify' item with a provenance-carried fact.
- Owner line-by-line review.
