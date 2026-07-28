---
name: jetson-boot-flashing
description: initrd flash, UEFI, A/B rootfs, massflash. DRAFT methodology pack, unreviewed, no paired golden.
applies_to: JetPack 6.x / L4T r36.x
tier: T1
status: draft-unreviewed
---

# jetson-boot-flashing (draft, unreviewed)

> Status: DRAFT. Not owner-reviewed and has no paired golden, so it does
> not yet meet the Part A3 skill contract. Methodology only: every
> device-specific value below is deliberately deferred to retrieval or
> on-hardware measurement, never asserted from memory (CLAUDE.md s1, s23).

Scope: initrd flash, UEFI, A/B rootfs, massflash.

## Methodology and traps

- Initrd flash and full flash fail differently: capture the host-side flash log and the target UART, not just the exit code.
- A/B rootfs means a bad update should roll back, not brick; verify the fallback slot boots before trusting an update path.
- Massflash needs identical BSP and signing state across units; a mismatched key or BSP silently produces unbootable units.
- UEFI variable state persists across flashes and can override boot order; clear or account for it when a freshly flashed unit boots the wrong slot.

## Retrieve or verify (do not assume)

- the flashing command and config for the specific carrier and module (from the BSP, verified on one unit first).
- signing/fuse state required for production flash.
- A/B slot layout and rollback trigger for this L4T.

## Before this becomes a real skill

- Pair it with a golden that fails or exceeds loop budget without it.
- Replace each 'retrieve or verify' item with a provenance-carried fact.
- Owner line-by-line review.
