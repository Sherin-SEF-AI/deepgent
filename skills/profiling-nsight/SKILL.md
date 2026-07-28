---
name: profiling-nsight
description: nsys/ncu timelines, bottleneck attribution. DRAFT methodology pack, unreviewed, no paired golden.
tier: T1
status: draft-unreviewed
---

# profiling-nsight (draft, unreviewed)

> Status: DRAFT. Not owner-reviewed and has no paired golden, so it does
> not yet meet the Part A3 skill contract. Methodology only: every
> device-specific value below is deliberately deferred to retrieval or
> on-hardware measurement, never asserted from memory (CLAUDE.md s1, s23).

Scope: nsys/ncu timelines, bottleneck attribution.

## Methodology and traps

- Attribute before optimizing: nsys for the timeline (is it GPU-bound?), ncu for the kernel (why?).
- A gap on the GPU timeline is usually CPU, sync, or copy, not slow kernels; fix the real bottleneck.
- Profile the steady state, not warm-up; first iterations mislead.

## Retrieve or verify (do not assume)

- the target GPU arch for ncu metric interpretation.

## Before this becomes a real skill

- Pair it with a golden that fails or exceeds loop budget without it.
- Replace each 'retrieve or verify' item with a provenance-carried fact.
- Owner line-by-line review.
