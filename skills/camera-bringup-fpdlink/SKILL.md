---
name: camera-bringup-fpdlink
description: FPD-Link III camera bring-up.
applies_to: TI DS90UB953 serializer / DS90UB960 deserializer
status: fact-verified
---

# camera-bringup-fpdlink

> Fact-verified: the facts below were retrieved from public datasheets
> ingested into the knowledge corpus and each cites its source document
> and section. No value is asserted from memory. Board-specific wiring and
> full register maps still require the complete datasheet or on-hardware
> verification. Needs a paired golden and owner review for full Part A3.

Scope: FPD-Link III camera bring-up.

When to reach for it: Bringing up a camera over an FPD-Link III serializer/deserializer link.

## Methodology

- Establish the link and the bidirectional control channel before the imager is addressable; the imager is reached through the deserializer's back-channel I2C, not directly.
- Match the serializer's CSI-2 input lane count to the sensor output and the deserializer's aggregation config; a lane-count mismatch yields corrupt or no frames.
- Gate bring-up steps on the link being up; do not configure the sensor before the deserializer reports the forward channel established.

## Verified facts (with provenance)

- The deserializer-side I2C controller must support I2C clock stretching for the FPD-Link III bidirectional control channel (DS90UB960 datasheet, Fig 7-26 / app note SNLA131).
- The DS90UB953 CSI-2 input is compliant with MIPI D-PHY v1.2 and CSI-2 v1.3, and supports one, two, or four differential data lanes plus a clock lane (DS90UB953 datasheet, s7.2.2.1).
- After power-up the CSI-2 input ignores all LP control data for an initial window (TINIT_TIME, default 100 microseconds, configurable) across all lanes (DS90UB953 datasheet, TINIT_TIME register).
- The DS90UB960 aggregates up to four FPD-Link III inputs onto one MIPI CSI-2 output, pairing with serializers such as the DS90UB953 (DS90UB960 datasheet, s7.1.1).

## Retrieve or verify (still needed)

- the exact serializer/deserializer register init order and the I2C alias map for your camera count (from the datasheet register maps).
- the forward-channel data rate and CSI-2 lane config for your sensor's pixel clock.
