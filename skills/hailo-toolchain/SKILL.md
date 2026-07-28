---
name: hailo-toolchain
description: DFC, HEF compile, quantization, model zoo. DRAFT methodology pack, unreviewed, no paired golden.
tier: T1
status: draft-unreviewed
---

# hailo-toolchain (draft, unreviewed)

> Status: DRAFT. Not owner-reviewed and has no paired golden, so it does
> not yet meet the Part A3 skill contract. Methodology only: every
> device-specific value below is deliberately deferred to retrieval or
> on-hardware measurement, never asserted from memory (CLAUDE.md s1, s23).

Scope: DFC, HEF compile, quantization, model zoo.

## Methodology and traps

- Compilation (DFC to HEF) is offline and quantization-aware; accuracy loss is decided at compile time, not runtime.
- The model must map to supported ops; an unsupported layer forces a CPU fallback or a graph edit before compile.
- Validate the compiled HEF's accuracy on real data, not only the compiler's estimate.

## Retrieve or verify (do not assume)

- the Hailo toolchain version and its supported-op list.
- the calibration set for quantization.

## Before this becomes a real skill

- Pair it with a golden that fails or exceeds loop budget without it.
- Replace each 'retrieve or verify' item with a provenance-carried fact.
- Owner line-by-line review.
