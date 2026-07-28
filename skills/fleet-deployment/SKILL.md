---
name: fleet-deployment
description: OTA, staged rollout, rollback criteria.
status: methodology-complete
---

# fleet-deployment

> Methodology skill: durable engineering practice, not device facts. It
> asserts no hardware-specific value; where a number depends on your
> stack or device, it says to measure or retrieve it. Still needs a
> paired golden and owner review to meet the full Part A3 contract.

Scope: OTA, staged rollout, rollback criteria.

When to reach for it: Rolling a software or model update across a device fleet safely.

## Methodology

- Stage every rollout (canary, then cohort, then fleet) with the rollback criteria defined before the rollout starts, not improvised during an incident.
- Gate each stage on health signals (crash rate, key metric, resource use); deploying without observability to gate on is deploying blind.
- Version and pin what each cohort runs so a regression is attributable to a specific change and a rollback is exact.
- Ensure the update mechanism itself has a proven rollback (A/B or equivalent); an OTA path that cannot roll back is a fleet-brick risk.

## Common traps

- A 'quick fix' pushed fleet-wide with no canary because it seemed safe.
- No pre-agreed rollback threshold, so the team argues during the incident.

## Definition of done

- Rollout is staged with health gates and a tested rollback; each cohort's exact version is recorded.
