---
name: cv-eval-metrics
description: mAP variants, HOTA/MOTA, calibration curves.
status: methodology-complete
---

# cv-eval-metrics

> Methodology skill: durable engineering practice, not device facts. It
> asserts no hardware-specific value; where a number depends on your
> stack or device, it says to measure or retrieve it. Still needs a
> paired golden and owner review to meet the full Part A3 contract.

Scope: mAP variants, HOTA/MOTA, calibration curves.

When to reach for it: Reporting or comparing perception accuracy so numbers are actually comparable.

## Methodology

- State the exact metric definition: which IoU thresholds (0.5 vs 0.5:0.95), area ranges, and per-class averaging. mAP numbers are not comparable across these choices.
- Report on the deployment distribution and slice by condition (night, rain, range); a dataset-average metric hides the failure modes that get someone hurt.
- Check confidence calibration (reliability diagram, ECE) when a downstream consumer (tracker, planner, fusion) uses the score; a high-AP model with miscalibrated confidence misleads them.
- For tracking, prefer HOTA (decomposable into detection and association accuracy) over MOTA alone.

## Common traps

- Comparing COCO-style mAP@[.5:.95] against VOC mAP@.5 as if equal.
- A single aggregate metric that hides a catastrophic slice (e.g. zero recall at night).

## Definition of done

- Metric definition and eval split agreed and recorded; results sliced by operating condition.
- Calibration reported when scores feed a downstream consumer.
