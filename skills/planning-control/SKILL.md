---
name: planning-control
description: MPC, pure pursuit, Stanley, lateral/longitudinal.
status: methodology-complete
---

# planning-control

> Methodology skill: durable engineering practice, not device facts. It
> asserts no hardware-specific value; where a number depends on your
> stack or device, it says to measure or retrieve it. Still needs a
> paired golden and owner review to meet the full Part A3 contract.

Scope: MPC, pure pursuit, Stanley, lateral/longitudinal.

When to reach for it: Lateral and longitudinal control of a vehicle across its speed range.

## Methodology

- Lateral and longitudinal control decouple at low speed but couple at high speed (load transfer, tire slip); validate across the full speed range, not one operating point.
- Pure pursuit and Stanley have known, opposite failure modes (corner-cutting vs high-speed oscillation); pick per speed/geometry and tune the lookahead/gain to the platform.
- MPC is only as good as its vehicle model and constraint set; an infeasible constraint silently degrades to poor or no control, so check feasibility and add slack deliberately.
- Rate-limit and saturate actuator commands in the controller, matched to the vehicle interface's real limits, so the plan never asks for impossible actuation.

## Common traps

- Tuning a controller at parking speed and shipping it to highway speed.
- An MPC whose constraints are occasionally infeasible, degrading without a clear signal.

## Definition of done

- Tracking error bounded across the speed range; commands respect actuation limits; MPC feasibility monitored.
