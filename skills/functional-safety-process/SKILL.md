---
name: functional-safety-process
description: 26262/21448 workflow, own words only. DRAFT methodology pack, unreviewed, no paired golden.
tier: T3
status: draft-unreviewed
---

# functional-safety-process (draft, unreviewed)

> Status: DRAFT. Not owner-reviewed and has no paired golden, so it does
> not yet meet the Part A3 skill contract. Own-words only: no licensed
> standard text is reproduced here (CLAUDE.md s6, s23). Clause-specific
> content must come from the licensed standard, not this pack.

Scope: 26262/21448 workflow, own words only.

## Methodology and traps

- Safety is an evidence trail, not a code property: requirements, hazard analysis, and verification must be traceable end to end.
- Define the item and its operational design domain before any hazard analysis; scope errors invalidate everything downstream.
- Separate random-fault safety from functional-insufficiency safety: the latter (SOTIF-style) is 'the system worked as designed and was still unsafe'.
- Every safety requirement traces to a verification result; an untraced requirement is an untested one.
- Keep the process artifacts versioned with the code so an audit can reconstruct why a decision was made.

## Retrieve or verify (do not assume)

- the applicable standard version, clause text, and ASIL/severity tables (from the licensed standard, never reproduced here).
- the project's safety plan and hazard analysis, owner-authored and reviewed.

## Before this becomes a real skill

- Pair it with a golden that fails or exceeds loop budget without it.
- Owner line-by-line review.
