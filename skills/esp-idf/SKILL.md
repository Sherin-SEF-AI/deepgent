---
name: esp-idf
description: partitions, WiFi/BLE, OTA. DRAFT methodology pack, unreviewed, no paired golden.
tier: T2
status: draft-unreviewed
---

# esp-idf (draft, unreviewed)

> Status: DRAFT. Not owner-reviewed and has no paired golden, so it does
> not yet meet the Part A3 skill contract. Methodology only: every
> device-specific value below is deliberately deferred to retrieval or
> on-hardware measurement, never asserted from memory (CLAUDE.md s1, s23).

Scope: partitions, WiFi/BLE, OTA.

## Methodology and traps

- Partition table and flash size must match the device; an OTA that fits in dev fails on a smaller production part.
- WiFi/BLE coexistence shares the radio; concurrent use needs explicit config or one starves.
- OTA needs a rollback and a validity check; a bad image without rollback bricks the field unit.

## Retrieve or verify (do not assume)

- the exact ESP part, flash size, and partition scheme.

## Before this becomes a real skill

- Pair it with a golden that fails or exceeds loop budget without it.
- Replace each 'retrieve or verify' item with a provenance-carried fact.
- Owner line-by-line review.
