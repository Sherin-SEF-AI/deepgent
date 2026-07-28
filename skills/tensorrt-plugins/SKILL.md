---
name: tensorrt-plugins
description: custom layers, plugin registry, versioning. DRAFT methodology pack, unreviewed, no paired golden.
applies_to: TensorRT 10.x
tier: T2
status: draft-unreviewed
---

# tensorrt-plugins (draft, unreviewed)

> Status: DRAFT. Not owner-reviewed and has no paired golden, so it does
> not yet meet the Part A3 skill contract. Methodology only: every
> device-specific value below is deliberately deferred to retrieval or
> on-hardware measurement, never asserted from memory (CLAUDE.md s1, s23).

Scope: custom layers, plugin registry, versioning.

## Methodology and traps

- A custom plugin ties the engine to a plugin version; version the plugin and the engine together or deserialization fails.
- Plugin serialization must round-trip all state; a missing field deserializes to garbage without an error.
- Prefer a supported native op or a graph rewrite before writing a plugin; plugins are a maintenance liability.

## Retrieve or verify (do not assume)

- the TensorRT plugin API surface for the pinned version.
- the layer semantics the plugin must reproduce, verified against a reference.

## Before this becomes a real skill

- Pair it with a golden that fails or exceeds loop budget without it.
- Replace each 'retrieve or verify' item with a provenance-carried fact.
- Owner line-by-line review.
