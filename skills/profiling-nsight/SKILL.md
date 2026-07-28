---
name: profiling-nsight
description: nsys/ncu timelines, bottleneck attribution.
status: methodology-complete
---

# profiling-nsight

> Methodology skill: durable engineering practice, not device facts. It
> asserts no hardware-specific value; where a number depends on your
> stack or device, it says to measure or retrieve it. Still needs a
> paired golden and owner review to meet the full Part A3 contract.

Scope: nsys/ncu timelines, bottleneck attribution.

When to reach for it: Attributing where time goes before optimizing anything.

## Methodology

- Use the right tool for the question: nsys for the system timeline (is the workload even GPU-bound? where are the gaps?), ncu for a specific kernel (why is it slow?).
- A gap on the GPU timeline is usually CPU work, synchronization, or memory copy, not slow kernels; fix the actual dominant cost, not the most visible kernel.
- Profile steady state, not warm-up; the first iterations include allocation and JIT and mislead.
- Attribute before optimizing and re-measure after; an optimization that does not move the profiled bottleneck was the wrong one.

## Common traps

- Optimizing a kernel that is 5% of the timeline while a memcpy or sync is 40%.
- Reading warm-up iterations as representative.

## Definition of done

- The dominant cost is identified from a timeline and addressed; re-profile confirms it moved.
