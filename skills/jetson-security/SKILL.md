---
name: jetson-security
description: secure boot, fuses, disk encryption. DRAFT methodology pack, unreviewed, no paired golden.
applies_to: JetPack 6.x / L4T r36.x
tier: T3
status: draft-unreviewed
---

# jetson-security (draft, unreviewed)

> Status: DRAFT. Not owner-reviewed and has no paired golden, so it does
> not yet meet the Part A3 skill contract. Methodology only: every
> device-specific value below is deliberately deferred to retrieval or
> on-hardware measurement, never asserted from memory (CLAUDE.md s1, s23).

Scope: secure boot, fuses, disk encryption.

## Methodology and traps

- Fuse burning is irreversible: dry-run the entire secure-boot chain on a sacrificial unit before touching production fuses.
- Secure boot, disk encryption, and signed kernel modules interact; enabling one can break an unsigned module or an A/B rollback path.
- Key custody is the hard part, not the crypto: define where signing keys live and who can use them before enabling secure boot.

## Retrieve or verify (do not assume)

- the fuse map and secure-boot enablement procedure for the module (owner-reviewed, tested on a sacrificial unit).
- disk-encryption options supported by this L4T and their boot-time cost.

## Before this becomes a real skill

- Pair it with a golden that fails or exceeds loop budget without it.
- Replace each 'retrieve or verify' item with a provenance-carried fact.
- Owner line-by-line review.
