---
name: serial-spi-i2c-debug
description: analyzer-driven reasoning, clock stretching. DRAFT methodology pack, unreviewed, no paired golden.
tier: T1
status: draft-unreviewed
---

# serial-spi-i2c-debug (draft, unreviewed)

> Status: DRAFT. Not owner-reviewed and has no paired golden, so it does
> not yet meet the Part A3 skill contract. Methodology only: every
> device-specific value below is deliberately deferred to retrieval or
> on-hardware measurement, never asserted from memory (CLAUDE.md s1, s23).

Scope: analyzer-driven reasoning, clock stretching.

## Methodology and traps

- Reason from the analyzer trace, not the symptom: capture the bus and read ACK/NAK, clock, and framing before touching code.
- I2C clock stretching by a slow slave hangs masters that do not support it; check for stretched clocks when a bus locks up.
- SPI mode (CPOL/CPHA) and bit order mismatches produce plausible-looking garbage; verify mode against the device.
- Pull-up sizing and bus capacitance shape I2C edges; marginal edges fail only at higher speeds or longer runs.

## Retrieve or verify (do not assume)

- the device's bus mode, max clock, and addressing (from its datasheet).
- the board's pull-up values and bus topology.

## Before this becomes a real skill

- Pair it with a golden that fails or exceeds loop budget without it.
- Replace each 'retrieve or verify' item with a provenance-carried fact.
- Owner line-by-line review.
