---
name: sensor-fusion-estimation
description: EKF/UKF/ESKF, robot_localization.
status: methodology-complete
---

# sensor-fusion-estimation

> Methodology skill: durable engineering practice, not device facts. It
> asserts no hardware-specific value; where a number depends on your
> stack or device, it says to measure or retrieve it. Still needs a
> paired golden and owner review to meet the full Part A3 contract.

Scope: EKF/UKF/ESKF, robot_localization.

When to reach for it: Fusing noisy, time-offset sensor streams into a state estimate.

## Methodology

- Set process and measurement noise from measured sensor characteristics (see the IMU/GNSS characterization), not by trial and error; the filter is only as good as its noise model.
- Time-align inputs: a fixed per-sensor latency offset is usually required, and unmodeled latency shows as a lagging or oscillating estimate.
- Monitor filter consistency (innovation / normalized innovation squared); an EKF diverges silently under bad initialization or unmodeled nonlinearity, and NIS reveals it before the estimate looks wrong.
- Prefer an ESKF for orientation-heavy problems; it keeps the error state small and linearization valid where a direct EKF on a quaternion struggles.

## Common traps

- Tuning noise until the output looks smooth (which just means overconfident/underconfident), rather than to consistency.
- Ignoring per-sensor time offsets and blaming the model.

## Definition of done

- NIS/innovation within expected bounds; noise params traced to measured sensor specs; time offsets applied.
