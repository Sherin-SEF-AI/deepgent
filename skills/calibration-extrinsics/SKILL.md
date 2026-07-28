---
name: calibration-extrinsics
description: cam-lidar, cam-imu, targetless.
status: methodology-complete
---

# calibration-extrinsics

> Methodology skill: durable engineering practice, not device facts. It
> asserts no hardware-specific value; where a number depends on your
> stack or device, it says to measure or retrieve it. Still needs a
> paired golden and owner review to meet the full Part A3 contract.

Scope: cam-lidar, cam-imu, targetless.

When to reach for it: Producing and maintaining the extrinsic transforms fusion depends on.

## Methodology

- Treat extrinsics as a measured, versioned artifact with an uncertainty, not a one-time constant; error propagates into every fusion product.
- Targetless methods are convenient but need motion excitation and good time sync; validate a targetless result against a target-based one at least once per rig design.
- Re-calibrate after any mechanical change; a bumped or re-seated sensor silently invalidates prior extrinsics.
- Report a validation metric (reprojection error, point-to-plane residual) with each calibration so a bad one is caught before it ships.

## Common traps

- Reusing extrinsics across physically different units of the 'same' rig.
- Accepting a targetless calibration with no independent validation.

## Definition of done

- Extrinsics versioned with an uncertainty and a validation metric; re-calibration triggered on mechanical change.
