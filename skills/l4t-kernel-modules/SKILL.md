---
name: l4t-kernel-modules
description: out-of-tree builds, headers, signing. DRAFT methodology pack, unreviewed, no paired golden.
applies_to: JetPack 6.x / L4T r36.x
tier: T1
status: draft-unreviewed
---

# l4t-kernel-modules (draft, unreviewed)

> Status: DRAFT. Not owner-reviewed and has no paired golden, so it does
> not yet meet the Part A3 skill contract. Methodology only: every
> device-specific value below is deliberately deferred to retrieval or
> on-hardware measurement, never asserted from memory (CLAUDE.md s1, s23).

Scope: out-of-tree builds, headers, signing.

## Methodology and traps

- Out-of-tree modules must be built against the exact running kernel's headers and version magic; a mismatch fails to load with a vermagic error.
- Module signing state is enforced or not depending on secure-boot config; test load on a representative unit, not only the dev unit.
- Rebuild after every BSP bump: kernel ABI is not stable across L4T point releases.
- Ship the KConfig and build steps with the module; a module that only builds on one workstation is not reproducible.

## Retrieve or verify (do not assume)

- the kernel source/headers package and version for this L4T.
- whether module signing is enforced by the board's secure-boot config.

## Before this becomes a real skill

- Pair it with a golden that fails or exceeds loop budget without it.
- Replace each 'retrieve or verify' item with a provenance-carried fact.
- Owner line-by-line review.
