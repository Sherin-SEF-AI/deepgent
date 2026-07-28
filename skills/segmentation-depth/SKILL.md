---
name: segmentation-depth
description: semantic/instance segmentation and mono/stereo depth.
status: methodology-complete
---

# segmentation-depth

> Methodology skill: durable engineering practice, not device facts. It
> asserts no hardware-specific value; where a number depends on your
> stack or device, it says to measure or retrieve it. Still needs a
> paired golden and owner review to meet the full Part A3 contract.

Scope: semantic/instance segmentation and mono/stereo depth.

When to reach for it: Dense prediction tasks where the metric and geometry must be pinned first.

## Methodology

- Fix the task before the model: semantic (per-pixel class), instance (per-object mask), and panoptic (both) use different heads and different metrics (mIoU vs mask AP vs PQ).
- For stereo depth, error scales with range and inversely with baseline and texture; report depth error vs range in bins, never a single RMSE.
- Mono depth is scale-ambiguous; decide whether downstream needs metric depth (then supply a scale cue: camera height, known object, or a metric-trained model) or relative depth.
- Evaluate segmentation on boundary pixels separately; overall mIoU hides thin-structure and edge failure that matters for free-space and lane use.

## Common traps

- A single depth RMSE hides the fact that near-range is fine and far-range is unusable.
- Class imbalance inflates mIoU when a few large classes dominate; report per-class IoU.

## Definition of done

- Depth error reported per range bin; segmentation reported per class and at boundaries.
- Metric-vs-relative depth decision made explicit and matched to downstream need.
