---
name: jetson-multimedia-api
description: libargus, NvBufSurface, EGL interop. DRAFT methodology pack, unreviewed, no paired golden.
applies_to: JetPack 6.x / L4T r36.x
tier: T1
status: draft-unreviewed
---

# jetson-multimedia-api (draft, unreviewed)

> Status: DRAFT. Not owner-reviewed and has no paired golden, so it does
> not yet meet the Part A3 skill contract. Methodology only: every
> device-specific value below is deliberately deferred to retrieval or
> on-hardware measurement, never asserted from memory (CLAUDE.md s1, s23).

Scope: libargus, NvBufSurface, EGL interop.

## Methodology and traps

- Keep frames in NvBufSurface end to end; a single copy to CPU memory for convenience erases the zero-copy win and dominates latency.
- libargus capture requests are asynchronous: measure glass-to-glass, not the API call, or you miss ISP and queue latency.
- EGL interop requires matching color format and memory layout on both sides; a mismatch shows as corrupt or black frames, not an error.
- Buffer pool exhaustion stalls the pipeline silently; size pools for the worst-case in-flight count and watch for starvation.

## Retrieve or verify (do not assume)

- the NvBufSurface formats and the ISP modes the sensor exposes through libargus.
- EGL/CUDA interop constraints for this L4T multimedia stack.

## Before this becomes a real skill

- Pair it with a golden that fails or exceeds loop budget without it.
- Replace each 'retrieve or verify' item with a provenance-carried fact.
- Owner line-by-line review.
