---
name: slam-localization
description: LIO-SAM family, map management, drift.
status: methodology-complete
---

# slam-localization

> Methodology skill: durable engineering practice, not device facts. It
> asserts no hardware-specific value; where a number depends on your
> stack or device, it says to measure or retrieve it. Still needs a
> paired golden and owner review to meet the full Part A3 contract.

Scope: LIO-SAM family, map management, drift.

When to reach for it: Building or localizing against a map where drift and loop closure govern quality.

## Methodology

- Drift is inevitable in odometry; the design question is loop closure and map management, not eliminating drift. Budget for it.
- LIO-family accuracy is bounded by IMU quality and lidar-IMU extrinsic calibration; bad extrinsics defeat a good algorithm, so calibrate first.
- Evaluate on a trajectory with ground truth or a loop-closure constraint, not by eyeballing a point cloud; a visually crisp map can still drift metrically.
- Manage map growth (voxel downsampling, keyframe selection, submaps) so long runs stay bounded in memory and compute.

## Common traps

- Judging SLAM by point-cloud sharpness rather than trajectory error.
- Unbounded map growth that degrades a long mission mid-run.

## Definition of done

- Trajectory error measured against ground truth or loop closure; map memory bounded over a long run.
