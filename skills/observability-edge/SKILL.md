---
name: observability-edge
description: metrics, log shipping, crash dumps.
status: methodology-complete
---

# observability-edge

> Methodology skill: durable engineering practice, not device facts. It
> asserts no hardware-specific value; where a number depends on your
> stack or device, it says to measure or retrieve it. Still needs a
> paired golden and owner review to meet the full Part A3 contract.

Scope: metrics, log shipping, crash dumps.

When to reach for it: Instrumenting fleet devices whose links are intermittent and storage is small.

## Methodology

- Buffer metrics and logs locally with bounded storage and forward opportunistically; the same store-and-forward discipline as telemetry applies.
- Prioritize crash dumps: they are the highest-value signal and are overwritten fast; capture and ship them before rotation.
- Control cardinality deliberately; high-cardinality labels explode storage and cost on constrained backends.
- Timestamp at the edge with a disciplined clock so events order correctly after delayed upload.

## Common traps

- High-cardinality per-device labels that blow up the metrics backend cost.
- Losing the crash dump to log rotation before it uploads.

## Definition of done

- Crash dumps reliably captured and shipped; metric cardinality bounded; buffering survives outages.
