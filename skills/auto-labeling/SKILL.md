---
name: auto-labeling
description: SAM-class, pseudo-labels, QA loops. DRAFT methodology pack, unreviewed, no paired golden.
tier: T2
status: draft-unreviewed
---

# auto-labeling (draft, unreviewed)

> Status: DRAFT. Not owner-reviewed and has no paired golden, so it does
> not yet meet the Part A3 skill contract. Methodology only: every
> device-specific value below is deliberately deferred to retrieval or
> on-hardware measurement, never asserted from memory (CLAUDE.md s1, s23).

Scope: SAM-class, pseudo-labels, QA loops.

## Methodology and traps

- Pseudo-labels need a QA gate; propagating a model's errors as labels bakes them in permanently.
- SAM-class tools speed masks but drift on domain-specific classes; sample-audit before trusting a batch.
- Track label provenance (auto vs human vs corrected) so a bad auto-label batch can be found and reverted.

## Retrieve or verify (do not assume)

- the acceptance threshold and audit rate for auto-labels.
- the class definitions and edge-case rules for the annotator model.

## Before this becomes a real skill

- Pair it with a golden that fails or exceeds loop budget without it.
- Replace each 'retrieve or verify' item with a provenance-carried fact.
- Owner line-by-line review.
