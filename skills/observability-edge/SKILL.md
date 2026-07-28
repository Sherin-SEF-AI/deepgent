---
name: observability-edge
description: metrics, log shipping, crash dumps. DRAFT methodology pack, unreviewed, no paired golden.
tier: T2
status: draft-unreviewed
---

# observability-edge (draft, unreviewed)

> Status: DRAFT. Not owner-reviewed and has no paired golden, so it does
> not yet meet the Part A3 skill contract. Methodology only: every
> device-specific value below is deliberately deferred to retrieval or
> on-hardware measurement, never asserted from memory (CLAUDE.md s1, s23).

Scope: metrics, log shipping, crash dumps.

## Methodology and traps

- Edge links are intermittent; buffer metrics and logs locally with bounded storage and forward opportunistically.
- Crash dumps are the highest-value signal; capture and ship them before they are overwritten.
- Cardinality kills edge telemetry cost; choose labels deliberately.

## Retrieve or verify (do not assume)

- the bandwidth/storage budget and the metrics backend contract.

## Before this becomes a real skill

- Pair it with a golden that fails or exceeds loop budget without it.
- Replace each 'retrieve or verify' item with a provenance-carried fact.
- Owner line-by-line review.
