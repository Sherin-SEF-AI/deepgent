---
name: containerization-edge
description: GPU passthrough, image size, runtime. DRAFT methodology pack, unreviewed, no paired golden.
tier: T1
status: draft-unreviewed
---

# containerization-edge (draft, unreviewed)

> Status: DRAFT. Not owner-reviewed and has no paired golden, so it does
> not yet meet the Part A3 skill contract. Methodology only: every
> device-specific value below is deliberately deferred to retrieval or
> on-hardware measurement, never asserted from memory (CLAUDE.md s1, s23).

Scope: GPU passthrough, image size, runtime.

## Methodology and traps

- GPU passthrough needs the container runtime configured (e.g. nvidia-container-toolkit); a plain runtime sees no GPU.
- Image size drives OTA cost and boot time on edge; multi-stage builds and a slim base matter more than on a server.
- Match the container's CUDA/runtime to the host driver; a newer runtime than the driver supports fails at load.

## Retrieve or verify (do not assume)

- the host driver version and the runtime's GPU-passthrough config.

## Before this becomes a real skill

- Pair it with a golden that fails or exceeds loop budget without it.
- Replace each 'retrieve or verify' item with a provenance-carried fact.
- Owner line-by-line review.
