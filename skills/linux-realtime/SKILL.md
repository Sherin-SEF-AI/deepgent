---
name: linux-realtime
description: PREEMPT_RT, isolation, affinity, priorities.
status: methodology-complete
---

# linux-realtime

> Methodology skill: durable engineering practice, not device facts. It
> asserts no hardware-specific value; where a number depends on your
> stack or device, it says to measure or retrieve it. Still needs a
> paired golden and owner review to meet the full Part A3 contract.

Scope: PREEMPT_RT, isolation, affinity, priorities.

When to reach for it: A workload needs bounded worst-case latency, not just good average.

## Methodology

- Optimize and measure worst-case, not mean: cyclictest under representative load reports max latency, which is what determinism means. A good average with a bad tail fails.
- Align isolation, IRQ affinity, and thread priority together: isolating a core but leaving interrupts or kernel threads on it defeats the isolation.
- Keep the hot path RT-safe: lock memory (mlockall), avoid dynamic allocation, page faults, and non-deterministic syscalls in the critical section.
- PREEMPT_RT lowers worst-case preemption latency but does not make a badly-written path deterministic; the code discipline still matters.

## Common traps

- Reporting mean latency for a real-time claim.
- A single page fault or malloc in the hot loop injecting a millisecond spike.

## Definition of done

- cyclictest max latency under load meets the deadline; hot path is allocation- and fault-free.
