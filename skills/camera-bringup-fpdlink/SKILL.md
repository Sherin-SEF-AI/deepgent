---
name: camera-bringup-fpdlink
description: FPD-Link camera bring-up. DRAFT methodology pack, unreviewed, no paired golden.
tier: T2
status: draft-unreviewed
---

# camera-bringup-fpdlink (draft, unreviewed)

> Status: DRAFT. Not owner-reviewed and has no paired golden, so it does
> not yet meet the Part A3 skill contract. Methodology only: every
> device-specific value below is deliberately deferred to retrieval or
> on-hardware measurement, never asserted from memory (CLAUDE.md s1, s23).

Scope: FPD-Link camera bring-up.

## Methodology and traps

- FPD-Link bring-up mirrors GMSL: establish the link and back-channel I2C before the imager is addressable.
- Back-channel (control) and forward-channel (video) can lock independently; confirm both.
- Deserializer output format must match the downstream CSI receiver expectation, not just the sensor output.

## Retrieve or verify (do not assume)

- the FPD-Link ser/des register set and lock indicators (from the datasheet).
- back-channel I2C addressing for the imager behind the link.

## Before this becomes a real skill

- Pair it with a golden that fails or exceeds loop budget without it.
- Replace each 'retrieve or verify' item with a provenance-carried fact.
- Owner line-by-line review.
