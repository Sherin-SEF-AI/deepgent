---
name: gnss-rtk
description: NTRIP, fix quality, UBX/NMEA.
applies_to: u-blox ZED-F9P multi-band RTK GNSS
status: fact-verified
---

# gnss-rtk

> Fact-verified: the facts below were retrieved from public datasheets
> ingested into the knowledge corpus and each cites its source document
> and section. No value is asserted from memory. Board-specific wiring and
> full register maps still require the complete datasheet or on-hardware
> verification. Needs a paired golden and owner review for full Part A3.

Scope: NTRIP, fix quality, UBX/NMEA.

When to reach for it: Integrating a multi-band RTK GNSS receiver for high-precision positioning.

## Methodology

- Gate downstream use on the fix type (float vs fixed), not the reported covariance alone.
- Monitor correction age and baseline length; both bound achievable accuracy.
- Parse the receiver's binary protocol (UBX) for the full solution; NMEA precision is often lower than the receiver's internal estimate.

## Verified facts (with provenance)

- The ZED-F9P is a multi-band (multi-constellation) RTK receiver providing fast convergence (u-blox ZED-F9P datasheet, abstract).
- RTK convergence time is under 10 s in multi-constellation modes (for example GPS+GLO+GAL+BDS) and under 30 s in GPS-only mode (u-blox ZED-F9P datasheet, page 5 Table 2).

## Retrieve or verify (still needed)

- the horizontal-accuracy figures for your antenna and correction source (datasheet table, confirmed in your environment).
- your NTRIP mountpoint and the baseline to it for the deployment area.
