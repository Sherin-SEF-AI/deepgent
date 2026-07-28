---
name: memory-debugging
description: ASAN/valgrind on edge, leak hunting.
status: methodology-complete
---

# memory-debugging

> Methodology skill: durable engineering practice, not device facts. It
> asserts no hardware-specific value; where a number depends on your
> stack or device, it says to measure or retrieve it. Still needs a
> paired golden and owner review to meet the full Part A3 contract.

Scope: ASAN/valgrind on edge, leak hunting.

When to reach for it: Chasing memory corruption or leaks in edge/C/C++ code.

## Methodology

- Run ASAN on the x86 build in CI first; it catches most heap/stack overflows and use-after-free cheaply, before you debug on the slow edge device.
- Use valgrind/memcheck for uninitialized-read and leak classes ASAN misses; accept its slowdown for the classes it uniquely finds.
- On the edge device a slow leak shows as an OOM after hours; trend RSS over a soak run rather than sampling once, and attribute growth to an allocation site.
- Reproduce with the smallest input that triggers it; an intermittent corruption under full load is often a specific race, DMA, or lifetime bug that a minimal case exposes.

## Common traps

- Assuming 'no crash in 10 minutes' means no leak; leaks show over hours.
- ASAN-clean but valgrind-dirty (uninitialized reads) shipping to the field.

## Definition of done

- ASAN and valgrind clean on the reproducer; RSS flat over a soak.
