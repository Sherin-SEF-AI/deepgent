---
name: bootloaders-ota
description: A/B updates, rollback, signing. DRAFT methodology pack, unreviewed, no paired golden.
tier: T2
status: draft-unreviewed
---

# bootloaders-ota (draft, unreviewed)

> Status: DRAFT. Not owner-reviewed and has no paired golden, so it does
> not yet meet the Part A3 skill contract. Methodology only: every
> device-specific value below is deliberately deferred to retrieval or
> on-hardware measurement, never asserted from memory (CLAUDE.md s1, s23).

Scope: A/B updates, rollback, signing.

## Methodology and traps

- A/B with rollback is the baseline; an update path without a proven rollback is a field-brick risk.
- Sign and verify images; an unauthenticated OTA is a remote-code-execution path.
- Power-fail during update must leave a bootable slot; test the update across a forced power cut.

## Retrieve or verify (do not assume)

- the bootloader's slot layout, signing scheme, and rollback trigger.

## Before this becomes a real skill

- Pair it with a golden that fails or exceeds loop budget without it.
- Replace each 'retrieve or verify' item with a provenance-carried fact.
- Owner line-by-line review.
