---
name: onnx-export-surgery
description: opsets, dynamic shapes, graph edits. DRAFT methodology pack, unreviewed, no paired golden.
tier: T0
status: draft-unreviewed
---

# onnx-export-surgery (draft, unreviewed)

> Status: DRAFT. Not owner-reviewed and has no paired golden, so it does
> not yet meet the Part A3 skill contract. Methodology only: every
> device-specific value below is deliberately deferred to retrieval or
> on-hardware measurement, never asserted from memory (CLAUDE.md s1, s23).

Scope: opsets, dynamic shapes, graph edits.

## Methodology and traps

- Pin the opset to what the target runtime supports; a newer opset exports cleanly and fails at load.
- Dynamic shapes must be declared at export, not patched later; a static-shape export cannot be made dynamic downstream.
- Verify numerics after any graph edit with a reference input; a folded or fused graph can silently change outputs.
- Strip training-only nodes (dropout, aux heads) before export to avoid runtime surprises.

## Retrieve or verify (do not assume)

- the opset and operator support of the target runtime/TensorRT version (from versions.toml / runtime docs).

## Before this becomes a real skill

- Pair it with a golden that fails or exceeds loop budget without it.
- Replace each 'retrieve or verify' item with a provenance-carried fact.
- Owner line-by-line review.
