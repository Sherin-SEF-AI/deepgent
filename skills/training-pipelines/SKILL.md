---
name: training-pipelines
description: dataloaders, AMP, schedulers, reproducibility.
status: methodology-complete
---

# training-pipelines

> Methodology skill: durable engineering practice, not device facts. It
> asserts no hardware-specific value; where a number depends on your
> stack or device, it says to measure or retrieve it. Still needs a
> paired golden and owner review to meet the full Part A3 contract.

Scope: dataloaders, AMP, schedulers, reproducibility.

When to reach for it: Any model training or fine-tune where results must be reproducible and debuggable.

## Methodology

- Fix and log every source of randomness (framework seed, cudnn deterministic flag, dataloader worker seeding) plus the data version hash and the code commit; store them in the run manifest so any run can be re-created.
- Treat the input pipeline as a first-class perf target: measure samples/s from the dataloader in isolation; if it is below GPU consumption rate, the GPU starves and more compute will not help.
- Use mixed precision (AMP) with a loss scaler, but validate final accuracy at the deployment precision, not fp32, because AMP changes numerics near the noise floor.
- Checkpoint optimizer, scheduler, scaler, and RNG state together with weights; a resume that restores only weights silently diverges from an uninterrupted run.
- Separate the LR warmup and decay schedule from the optimizer; log the effective LR each step so a schedule bug is visible, not inferred.
- Validate on a fixed, versioned split at a fixed cadence; a moving val set makes early-stopping and comparison meaningless.
- Gradient accumulation emulates a larger batch but interacts with BatchNorm and LR scaling; scale LR to the effective batch and prefer GroupNorm/SyncBN when accumulating.

## Common traps

- Non-deterministic dataloader worker order changes augmentation draw order and makes 'same seed' runs differ; seed workers explicitly.
- Logging train accuracy from the AMP-scaled loss instead of the unscaled metric hides real progress.
- Silent NaNs from an over-aggressive loss scale look like a plateau; watch the scaler's skipped-step count.

## Definition of done

- Two runs with the same seed and data version produce the same val curve within noise.
- Dataloader throughput exceeds steady-state GPU consumption.
- A killed run resumes to a curve indistinguishable from an uninterrupted one.
