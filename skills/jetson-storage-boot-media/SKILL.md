---
name: jetson-storage-boot-media
description: NVMe boot, eMMC, SD. DRAFT methodology pack, unreviewed, no paired golden.
applies_to: JetPack 6.x / L4T r36.x
tier: T2
status: draft-unreviewed
---

# jetson-storage-boot-media (draft, unreviewed)

> Status: DRAFT. Not owner-reviewed and has no paired golden, so it does
> not yet meet the Part A3 skill contract. Methodology only: every
> device-specific value below is deliberately deferred to retrieval or
> on-hardware measurement, never asserted from memory (CLAUDE.md s1, s23).

Scope: NVMe boot, eMMC, SD.

## Methodology and traps

- NVMe boot vs eMMC vs SD changes the boot chain, not just capacity; a device-tree/bootloader change is usually required to move root.
- SD cards vary wildly in sustained write and endurance; a logging workload that passes on one card corrupts on another.
- Measure real sequential and random IO on the target medium; datasheet numbers are best-case and rarely met on edge carriers.

## Retrieve or verify (do not assume)

- the boot-order and root-device configuration steps for NVMe/eMMC/SD on this carrier.
- endurance and sustained-write specs for the chosen medium (from its datasheet).

## Before this becomes a real skill

- Pair it with a golden that fails or exceeds loop budget without it.
- Replace each 'retrieve or verify' item with a provenance-carried fact.
- Owner line-by-line review.
