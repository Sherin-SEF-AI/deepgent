---
name: firmware-debugging
description: JTAG/SWD, hard fault analysis, tracing. DRAFT methodology pack, unreviewed, no paired golden.
tier: T2
status: draft-unreviewed
---

# firmware-debugging (draft, unreviewed)

> Status: DRAFT. Not owner-reviewed and has no paired golden, so it does
> not yet meet the Part A3 skill contract. Methodology only: every
> device-specific value below is deliberately deferred to retrieval or
> on-hardware measurement, never asserted from memory (CLAUDE.md s1, s23).

Scope: JTAG/SWD, hard fault analysis, tracing.

## Methodology and traps

- A hard fault has a recoverable trail: capture the stacked registers and fault status before resetting.
- JTAG/SWD lets you halt and inspect; a printf-only workflow misses timing and fault state.
- Reproduce with a minimal case; an intermittent fault under the full app is often a stack, DMA, or interrupt-priority bug.

## Retrieve or verify (do not assume)

- the core's fault-status registers and debug interface (from the reference manual).

## Before this becomes a real skill

- Pair it with a golden that fails or exceeds loop budget without it.
- Replace each 'retrieve or verify' item with a provenance-carried fact.
- Owner line-by-line review.
