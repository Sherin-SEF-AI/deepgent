---
name: detection-architectures
description: YOLO family, DETR, anchor-free tradeoffs. DRAFT methodology pack, unreviewed, no paired golden.
tier: T1
status: draft-unreviewed
---

# detection-architectures (draft, unreviewed)

> Status: DRAFT. Not owner-reviewed and has no paired golden, so it does
> not yet meet the Part A3 skill contract. Methodology only: every
> device-specific value below is deliberately deferred to retrieval or
> on-hardware measurement, never asserted from memory (CLAUDE.md s1, s23).

Scope: YOLO family, DETR, anchor-free tradeoffs.

## Methodology and traps

- Anchor-based vs anchor-free changes label assignment and NMS behavior; a config tuned for one hurts the other.
- Report accuracy at the deployment input resolution and precision, not the training-time ideal.
- DETR-family models converge slowly and are sensitive to augmentation; do not compare to a YOLO on epoch count.

## Retrieve or verify (do not assume)

- the target latency/accuracy envelope on the deployment device.
- the class set and dataset the model must serve.

## Before this becomes a real skill

- Pair it with a golden that fails or exceeds loop budget without it.
- Replace each 'retrieve or verify' item with a provenance-carried fact.
- Owner line-by-line review.
