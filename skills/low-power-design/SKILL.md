---
name: low-power-design
description: sleep modes, wake sources, budgets.
status: methodology-complete
---

# low-power-design

> Methodology skill: durable engineering practice, not device facts. It
> asserts no hardware-specific value; where a number depends on your
> stack or device, it says to measure or retrieve it. Still needs a
> paired golden and owner review to meet the full Part A3 contract.

Scope: sleep modes, wake sources, budgets.

When to reach for it: Meeting a battery-life budget on an embedded device.

## Methodology

- Measure sleep current, do not estimate it; one peripheral or pull-up left enabled commonly dominates the budget and is invisible without a meter.
- Enumerate every wake source explicitly; an unexpected or chattering wake source drains the battery between real events.
- Duty cycle sets battery life more than active current for most sensing devices; optimize how often you wake and how long you stay up first.
- Build a power budget spreadsheet from measured per-state currents and real duty cycle, and validate it against a measured multi-hour run.

## Common traps

- A GPIO or peripheral left driven in sleep, multiplying sleep current.
- Optimizing active-mode efficiency when duty cycle is the real lever.

## Definition of done

- Measured sleep and active currents match the budget; battery-life estimate validated against a real run.
