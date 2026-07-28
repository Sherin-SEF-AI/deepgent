---
name: cuda-kernel-optimization
description: coalescing, occupancy, streams.
status: methodology-complete
---

# cuda-kernel-optimization

> Methodology skill: durable engineering practice, not device facts. It
> asserts no hardware-specific value; where a number depends on your
> stack or device, it says to measure or retrieve it. Still needs a
> paired golden and owner review to meet the full Part A3 contract.

Scope: coalescing, occupancy, streams.

When to reach for it: A CUDA kernel is the bottleneck and needs to be faster without becoming wrong.

## Methodology

- Profile before touching code: determine memory-bound vs compute-bound (from an ncu report). The fix is entirely different, and optimizing the wrong axis wastes effort.
- For memory-bound kernels, fix the access pattern first: coalesce global loads/stores, use shared memory for reuse, and align to the transaction size. This usually beats arithmetic cleverness.
- Raise occupancy only until latency is hidden, not maximally; past that, register/shared pressure hurts. Use the occupancy calculator as a guide, then measure.
- Overlap host-device copy with compute using streams and pinned memory only after the kernel itself is efficient; streaming a slow kernel hides nothing.
- Verify correctness against a CPU reference after every change; deepgent's cuda-check (compute-sanitizer) should be clean of races and memory errors.

## Common traps

- Chasing occupancy to 100% and slowing down due to register spills.
- Bank conflicts in shared memory silently serialize access; pad to avoid them.

## Definition of done

- ncu shows the kernel is bound by the intended resource and near roofline for it.
- compute-sanitizer clean; output matches the reference within tolerance.
