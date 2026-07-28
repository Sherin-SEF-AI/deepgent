---
name: rtos-zephyr
description: device model, threading, power management. DRAFT methodology pack, unreviewed, no paired golden.
tier: T2
status: draft-unreviewed
---

# rtos-zephyr (draft, unreviewed)

> Status: DRAFT. Not owner-reviewed and has no paired golden, so it does
> not yet meet the Part A3 skill contract. Methodology only: every
> device-specific value below is deliberately deferred to retrieval or
> on-hardware measurement, never asserted from memory (CLAUDE.md s1, s23).

Scope: device model, threading, power management.

## Methodology and traps

- The Zephyr device model binds drivers via device tree; a missing or wrong binding fails at build or silently at init.
- Thread priorities and stack sizes are unforgiving; a too-small stack corrupts silently, a bad priority starves a task.
- Power-management hooks must be implemented per driver; a single non-idle peripheral defeats system sleep.

## Retrieve or verify (do not assume)

- the board's Zephyr device-tree bindings and supported drivers.
- the peripheral power states for the target SoC.

## Before this becomes a real skill

- Pair it with a golden that fails or exceeds loop budget without it.
- Replace each 'retrieve or verify' item with a provenance-carried fact.
- Owner line-by-line review.
