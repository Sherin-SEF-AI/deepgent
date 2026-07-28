---
name: can-bus
description: SocketCAN, CAN-FD, sample point, bus-off recovery. DRAFT methodology pack, unreviewed, no paired golden.
tier: T0
status: draft-unreviewed
---

# can-bus (draft, unreviewed)

> Status: DRAFT. Not owner-reviewed and has no paired golden, so it does
> not yet meet the Part A3 skill contract. Methodology only: every
> device-specific value below is deliberately deferred to retrieval or
> on-hardware measurement, never asserted from memory (CLAUDE.md s1, s23).

Scope: SocketCAN, CAN-FD, sample point, bus-off recovery.

## Methodology and traps

- Set the sample point deliberately, not by default; the wrong sample point causes intermittent errors that look like wiring faults.
- CAN-FD bit-rate switching needs both nodes configured identically; a mismatch shows as bursts of error frames.
- Design bus-off recovery explicitly: a node that goes bus-off and never recovers is a silent single point of failure.
- Termination is 120 ohm at both physical ends only; extra or missing termination degrades signal integrity subtly.

## Retrieve or verify (do not assume)

- the bus nominal/data bitrate and required sample point for this network.
- the DBC / message layout for the devices on the bus.

## Before this becomes a real skill

- Pair it with a golden that fails or exceeds loop budget without it.
- Replace each 'retrieve or verify' item with a provenance-carried fact.
- Owner line-by-line review.
