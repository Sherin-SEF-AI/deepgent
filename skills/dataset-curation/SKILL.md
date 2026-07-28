---
name: dataset-curation
description: dedup, mining, splits, leakage prevention.
status: methodology-complete
---

# dataset-curation

> Methodology skill: durable engineering practice, not device facts. It
> asserts no hardware-specific value; where a number depends on your
> stack or device, it says to measure or retrieve it. Still needs a
> paired golden and owner review to meet the full Part A3 contract.

Scope: dedup, mining, splits, leakage prevention.

When to reach for it: Building or auditing a dataset whose splits must not leak.

## Methodology

- Split by the highest-correlation unit, not by frame: by scene, drive, or vehicle. Random per-frame splits leak near-identical neighbors from train into val and inflate every metric.
- Deduplicate near-duplicates (perceptual hash or embedding distance) before splitting; identical frames across splits are silent leakage.
- Mine for rare scenarios deliberately (hard-example mining, class-balanced sampling by scenario not by frame count); a frame-balanced dataset is scenario-imbalanced.
- Version the dataset and record the split keys and hashes in the manifest so a metric is attributable to a specific data state.

## Common traps

- Augmenting before splitting leaks an image's augmentations across splits.
- Balancing by class-frame-count still leaves rare-scenario classes underrepresented in the situations that matter.

## Definition of done

- Splits keyed by scene/drive/vehicle with no shared near-duplicates (verified by dedup pass).
- Rare-scenario coverage measured, not assumed from class counts.
