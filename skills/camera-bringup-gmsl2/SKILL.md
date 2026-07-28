---
name: camera-bringup-gmsl2
description: SerDes link config order, link-lock debug. DRAFT methodology pack, unreviewed, no paired golden.
tier: T1
status: draft-unreviewed
---

# camera-bringup-gmsl2 (draft, unreviewed)

> Status: DRAFT. Not owner-reviewed and has no paired golden, so it does
> not yet meet the Part A3 skill contract. Methodology only: every
> device-specific value below is deliberately deferred to retrieval or
> on-hardware measurement, never asserted from memory (CLAUDE.md s1, s23).

Scope: SerDes link config order, link-lock debug.

## Methodology and traps

- Link config order is the whole game: configure serializer and deserializer address translation and link rate before the sensor is reachable.
- Link-lock is a discrete signal; poll the deserializer lock status and gate all further steps on it rather than assuming.
- Address translation collisions across multiple cameras on one deserializer are a common silent failure; plan the I2C alias map up front.
- Cable length and quality affect lock at higher rates; a link that locks on the bench can fail in the vehicle harness.

## Retrieve or verify (do not assume)

- serializer/deserializer register maps and the link-rate/lock status registers (from the SerDes datasheet).
- the I2C alias/translation scheme for the camera count on this deserializer.

## Before this becomes a real skill

- Pair it with a golden that fails or exceeds loop budget without it.
- Replace each 'retrieve or verify' item with a provenance-carried fact.
- Owner line-by-line review.
