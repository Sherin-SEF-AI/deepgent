---
name: linux-realtime
description: PREEMPT_RT, isolation, affinity, priorities. DRAFT methodology pack, unreviewed, no paired golden.
tier: T1
status: draft-unreviewed
---

# linux-realtime (draft, unreviewed)

> Status: DRAFT. Not owner-reviewed and has no paired golden, so it does
> not yet meet the Part A3 skill contract. Methodology only: every
> device-specific value below is deliberately deferred to retrieval or
> on-hardware measurement, never asserted from memory (CLAUDE.md s1, s23).

Scope: PREEMPT_RT, isolation, affinity, priorities.

## Methodology and traps

- PREEMPT_RT lowers worst-case latency, not average; measure max latency under load with cyclictest, not mean.
- CPU isolation, IRQ affinity, and priority must align; isolating a core but leaving IRQs on it defeats the purpose.
- A non-RT-safe syscall or page fault in the hot path breaks determinism; lock memory and avoid dynamic allocation there.

## Retrieve or verify (do not assume)

- the kernel config (PREEMPT_RT vs stock) and isolable core count on the target.

## Before this becomes a real skill

- Pair it with a golden that fails or exceeds loop budget without it.
- Replace each 'retrieve or verify' item with a provenance-carried fact.
- Owner line-by-line review.
