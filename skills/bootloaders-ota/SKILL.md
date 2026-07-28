---
name: bootloaders-ota
description: A/B updates, rollback, signing.
status: methodology-complete
---

# bootloaders-ota

> Methodology skill: durable engineering practice, not device facts. It
> asserts no hardware-specific value; where a number depends on your
> stack or device, it says to measure or retrieve it. Still needs a
> paired golden and owner review to meet the full Part A3 contract.

Scope: A/B updates, rollback, signing.

When to reach for it: Designing a field-update path that cannot brick a device.

## Methodology

- A/B (or equivalent) with a proven rollback is the baseline; an update path without a tested rollback is a field-brick risk regardless of how careful the update is.
- Sign images and verify on the device before boot; an unauthenticated OTA is a remote-code-execution path.
- Make the update power-fail safe: a forced power cut mid-update must leave a bootable slot. Test exactly that.
- Gate the slot switch on a post-update health check (watchdog-confirmed boot) so a bad image auto-reverts.

## Common traps

- Testing the happy path only and never a power cut during flash.
- Switching the active slot before confirming the new image actually boots and passes health.

## Definition of done

- Update survives a mid-flash power cut with a bootable fallback; images signed/verified; auto-revert on failed health.
