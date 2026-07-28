---
name: auto-labeling
description: SAM-class tools, pseudo-labels, QA loops.
status: methodology-complete
---

# auto-labeling

> Methodology skill: durable engineering practice, not device facts. It
> asserts no hardware-specific value; where a number depends on your
> stack or device, it says to measure or retrieve it. Still needs a
> paired golden and owner review to meet the full Part A3 contract.

Scope: SAM-class tools, pseudo-labels, QA loops.

When to reach for it: Scaling annotation with model assistance while bounding error propagation.

## Methodology

- Gate every pseudo-label batch with a human-audited sample; propagating a model's systematic errors as labels bakes them in permanently and is hard to unwind.
- Track label provenance (auto / human / human-corrected) as metadata so a bad auto-batch is findable and revertable.
- Use confidence and agreement (ensemble or multi-view) to route only uncertain items to humans; spend annotation budget where the model is unsure.
- Re-audit auto-labels after any domain shift; a labeler model that was fine on day scenes drifts on night scenes.

## Common traps

- SAM-class mask tools drift on domain-specific or thin classes; a clean-looking mask can be systematically wrong at boundaries.
- Trusting model confidence as calibrated; auto-label acceptance needs a measured precision at the chosen threshold.

## Definition of done

- Measured precision of accepted auto-labels at the acceptance threshold.
- Provenance recorded per label; a batch can be found and reverted.
