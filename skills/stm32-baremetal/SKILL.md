---
name: stm32-baremetal
description: HAL vs LL, DMA, clock tree. DRAFT methodology pack, unreviewed, no paired golden.
tier: T2
status: draft-unreviewed
---

# stm32-baremetal (draft, unreviewed)

> Status: DRAFT. Not owner-reviewed and has no paired golden, so it does
> not yet meet the Part A3 skill contract. Methodology only: every
> device-specific value below is deliberately deferred to retrieval or
> on-hardware measurement, never asserted from memory (CLAUDE.md s1, s23).

Scope: HAL vs LL, DMA, clock tree.

## Methodology and traps

- HAL is fast to start and heavy; LL/register is lean and unforgiving; choose per resource budget and stick to one per driver.
- The clock tree is the root of most bring-up bugs; get the clock config right before any peripheral.
- DMA plus cache (on cached cores) needs explicit coherency handling; a missing cache-maintenance op yields stale data.

## Retrieve or verify (do not assume)

- the exact STM32 part, its clock tree, and peripheral mapping (from its reference manual).

## Before this becomes a real skill

- Pair it with a golden that fails or exceeds loop budget without it.
- Replace each 'retrieve or verify' item with a provenance-carried fact.
- Owner line-by-line review.
