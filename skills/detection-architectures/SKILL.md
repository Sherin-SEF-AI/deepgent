---
name: detection-architectures
description: YOLO family, DETR, anchor-free tradeoffs.
status: methodology-complete
---

# detection-architectures

> Methodology skill: durable engineering practice, not device facts. It
> asserts no hardware-specific value; where a number depends on your
> stack or device, it says to measure or retrieve it. Still needs a
> paired golden and owner review to meet the full Part A3 contract.

Scope: YOLO family, DETR, anchor-free tradeoffs.

When to reach for it: Choosing or tuning an object detector for an edge latency/accuracy budget.

## Methodology

- Pick the family by label-assignment behavior, not benchmark mAP: anchor-based needs anchor tuning to your box-size distribution; anchor-free (center/point) avoids that but is sensitive to scale imbalance; DETR-family removes NMS but converges slowly and wants heavy augmentation.
- Fix the evaluation input resolution and precision to the deployment target before comparing models; a model that wins at 1280px fp16 can lose at 640px int8.
- Tune NMS (IoU threshold, score threshold, class-agnostic vs per-class) on the val set; default NMS often costs several points of recall on crowded scenes.
- For small-object regimes, resolution and feature-pyramid level matter more than backbone size; measure per-size AP (small/medium/large), not just overall.

## Common traps

- Comparing a YOLO to a DETR on epoch count is meaningless; they have different convergence regimes.
- Reporting training-resolution mAP and deploying at a lower resolution overstates field accuracy.

## Definition of done

- Accuracy reported at the exact deployment resolution and precision, broken out by object size.
- NMS thresholds chosen from a sweep on the val set, not defaults.
