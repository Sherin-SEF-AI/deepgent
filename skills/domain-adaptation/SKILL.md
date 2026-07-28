---
name: domain-adaptation
description: night, rain, regional distribution shift.
status: methodology-complete
---

# domain-adaptation

> Methodology skill: durable engineering practice, not device facts. It
> asserts no hardware-specific value; where a number depends on your
> stack or device, it says to measure or retrieve it. Still needs a
> paired golden and owner review to meet the full Part A3 contract.

Scope: night, rain, regional distribution shift.

When to reach for it: A model that works in one domain must hold up in another.

## Methodology

- Quantify the gap first: measure the target-domain metric on the source model before adapting, or you cannot demonstrate improvement.
- Build a matched target-domain evaluation set (even small, even proxy-labeled); adapting without a target val set is guessing.
- Prefer the cheapest lever that closes the gap: targeted data collection and augmentation before adversarial or self-training methods, which add instability.
- Watch for negative transfer: adaptation that helps the target can regress the source; report both.

## Common traps

- Synthetic or heavily augmented target data introduces its own gap; validate on real target data.
- Improving an unlabeled target proxy metric that does not correlate with the real objective.

## Definition of done

- Target-domain metric measured before and after; source-domain regression checked.
