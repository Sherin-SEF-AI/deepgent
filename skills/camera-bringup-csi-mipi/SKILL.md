---
name: camera-bringup-csi-mipi
description: CSI/MIPI camera bring-up. DRAFT methodology pack, unreviewed, no paired golden.
tier: T0
status: draft-unreviewed
---

# camera-bringup-csi-mipi (draft, unreviewed)

> Status: DRAFT. Not owner-reviewed and has no paired golden, so it does
> not yet meet the Part A3 skill contract. Methodology only: every
> device-specific value below is deliberately deferred to retrieval or
> on-hardware measurement, never asserted from memory (CLAUDE.md s1, s23).

Scope: CSI/MIPI camera bring-up.

## Methodology and traps

- Bring-up order matters: power and clocks, then I2C probe, then streaming; a failure at streaming with a clean probe is usually lane/timing, not the driver.
- Lane count, lane mapping, and continuous-vs-discontinuous clock must match sensor config and the CSI receiver; a mismatch yields no frames or corrupt lines.
- Use the media-controller graph to confirm every link is enabled and formats negotiate; a disabled pad looks like a dead sensor.
- First light is a test pattern, not the sensor: prove the pipe with the sensor's internal pattern before blaming optics or exposure.

## Retrieve or verify (do not assume)

- the sensor's register init sequence and supported modes (from its datasheet / vendor driver, with provenance).
- CSI lane mapping and clock config for the carrier.
- I2C bus and address for the sensor on this board.

## Before this becomes a real skill

- Pair it with a golden that fails or exceeds loop budget without it.
- Replace each 'retrieve or verify' item with a provenance-carried fact.
- Owner line-by-line review.
