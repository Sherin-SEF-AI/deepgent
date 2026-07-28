---
name: containerization-edge
description: GPU passthrough, image size, runtime.
status: methodology-complete
---

# containerization-edge

> Methodology skill: durable engineering practice, not device facts. It
> asserts no hardware-specific value; where a number depends on your
> stack or device, it says to measure or retrieve it. Still needs a
> paired golden and owner review to meet the full Part A3 contract.

Scope: GPU passthrough, image size, runtime.

When to reach for it: Packaging edge inference workloads in containers with GPU access.

## Methodology

- GPU passthrough needs the container runtime configured (e.g. the NVIDIA container toolkit and `--gpus`); a stock runtime sees no GPU and silently runs on CPU or fails at init.
- Match the container's CUDA/runtime version to the host driver: a newer runtime than the driver supports fails at load. Forward compatibility (older runtime, newer driver) generally works.
- Image size drives OTA cost and cold-start on edge far more than on servers; use multi-stage builds, a slim runtime base (not a devel image in production), and copy only artifacts.
- Pin base images by digest, not floating tags, so a rebuild is reproducible.

## Common traps

- Shipping the devel image (with the full toolkit) to production, multiplying image size.
- A floating :latest base that changes CUDA under you between builds.

## Definition of done

- Container sees the GPU via the configured runtime; runtime/driver versions compatible; production image is slim and digest-pinned.
