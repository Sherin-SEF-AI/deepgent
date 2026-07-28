---
name: bev-occupancy
description: LSS/BEVFormer family, multi-cam to BEV.
status: methodology-complete
---

# bev-occupancy

> Methodology skill: durable engineering practice, not device facts. It
> asserts no hardware-specific value; where a number depends on your
> stack or device, it says to measure or retrieve it. Still needs a
> paired golden and owner review to meet the full Part A3 contract.

Scope: LSS/BEVFormer family, multi-cam to BEV.

When to reach for it: Fusing multiple camera views into a bird's-eye-view or occupancy grid.

## Methodology

- BEV quality depends on accurate camera intrinsics/extrinsics; small calibration error smears the projected grid, so calibrate before blaming the model.
- LSS-style depth-lifting and transformer-attention (BEVFormer-style) trade compute for accuracy differently; pick for the device budget and measure both latency and grid accuracy.
- Temporal fusion across frames improves occupancy but needs consistent ego-motion; verify pose quality before adding temporal terms.
- Choose grid resolution and range for the task; finer grids cost quadratic compute for diminishing planning benefit.

## Common traps

- Attributing BEV smearing to the network when the real cause is rig calibration.
- A grid resolution/range chosen for benchmark scores, not the planner's need or the device budget.

## Definition of done

- BEV accuracy measured against the calibrated rig; latency and grid config matched to device and planner needs.
