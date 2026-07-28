---
name: jetson-device-tree
description: pinmux, overlays, dtb build and flash. DRAFT methodology pack, unreviewed, no paired golden.
applies_to: JetPack 6.x / L4T r36.x
tier: T1
status: draft-unreviewed
---

# jetson-device-tree (draft, unreviewed)

> Status: DRAFT. Not owner-reviewed and has no paired golden, so it does
> not yet meet the Part A3 skill contract. Methodology only: every
> device-specific value below is deliberately deferred to retrieval or
> on-hardware measurement, never asserted from memory (CLAUDE.md s1, s23).

Scope: pinmux, overlays, dtb build and flash.

## Methodology and traps

- Prefer an overlay over editing the base dtb: overlays survive BSP upgrades, base edits get overwritten on flash.
- Pinmux and the device tree must agree: a pin claimed by two nodes builds cleanly and fails silently at runtime.
- Rebuild and reflash the dtb through the board's real boot path (extlinux/UEFI), not by hot-swapping the file, or you debug a stale tree.
- Validate the compiled dtb with a decompile-and-diff against intent before flashing; dtc accepts many bindings that the kernel ignores.

## Retrieve or verify (do not assume)

- the module's pinmux spreadsheet and valid mux options per ball.
- the exact compatible strings and required properties for each subdevice (from the kernel bindings, not memory).
- the board's dtb load path (extlinux.conf vs UEFI) for this L4T.

## Before this becomes a real skill

- Pair it with a golden that fails or exceeds loop budget without it.
- Replace each 'retrieve or verify' item with a provenance-carried fact.
- Owner line-by-line review.
