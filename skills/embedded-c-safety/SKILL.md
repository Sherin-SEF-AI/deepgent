---
name: embedded-c-safety
description: MISRA-oriented patterns, own words only. DRAFT methodology pack, unreviewed, no paired golden.
tier: T0
status: draft-unreviewed
---

# embedded-c-safety (draft, unreviewed)

> Status: DRAFT. Not owner-reviewed and has no paired golden, so it does
> not yet meet the Part A3 skill contract. Own-words only: no licensed
> standard text is reproduced here (CLAUDE.md s6, s23). Clause-specific
> content must come from the licensed standard, not this pack.

Scope: MISRA-oriented patterns, own words only.

## Methodology and traps

- Constrain the language to a safe subset: no dynamic allocation in the hot path, no unbounded recursion, bounded loops with a provable limit.
- Make integer width and signedness explicit; forbid implicit narrowing conversions that silently lose data.
- Every switch has a default and every if-else chain a final else; no unintentional fallthrough.
- Check every return value that can fail; an ignored error code is a latent fault.
- One disciplined cleanup/exit path; avoid goto except a single documented cleanup idiom.
- Enforce the rules with a static-analysis profile (clang-tidy + cppcheck), not review alone; deepgent's misra_gate blocks new violations on C/C++ writes.

## Retrieve or verify (do not assume)

- the exact coding-standard rule set the project commits to (the licensed standard text stays in the licensed document, never copied here).
- the static-analysis tool configuration that encodes those rules.

## Before this becomes a real skill

- Pair it with a golden that fails or exceeds loop budget without it.
- Owner line-by-line review.
