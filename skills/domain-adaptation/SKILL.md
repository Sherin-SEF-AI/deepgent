---
name: domain-adaptation
description: night, rain, regional traffic distributions. DRAFT methodology pack, unreviewed, no paired golden.
tier: T2
status: draft-unreviewed
---

# domain-adaptation (draft, unreviewed)

> Status: DRAFT. Not owner-reviewed and has no paired golden, so it does
> not yet meet the Part A3 skill contract. Methodology only: every
> device-specific value below is deliberately deferred to retrieval or
> on-hardware measurement, never asserted from memory (CLAUDE.md s1, s23).

Scope: night, rain, regional traffic distributions.

## Methodology and traps

- Quantify the domain gap before adapting: measure the target-domain metric first, or you cannot show improvement.
- Night/rain/region shifts need matched evaluation sets; adapting without a target-domain val set is guessing.
- Synthetic or augmented data helps but introduces its own gap; validate on real target data.

## Retrieve or verify (do not assume)

- a labeled or proxy evaluation set for the target domain.

## Before this becomes a real skill

- Pair it with a golden that fails or exceeds loop budget without it.
- Replace each 'retrieve or verify' item with a provenance-carried fact.
- Owner line-by-line review.
