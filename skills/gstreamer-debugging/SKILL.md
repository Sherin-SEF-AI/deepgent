---
name: gstreamer-debugging
description: pad probes, caps negotiation, latency tracing.
status: methodology-complete
---

# gstreamer-debugging

> Methodology skill: durable engineering practice, not device facts. It
> asserts no hardware-specific value; where a number depends on your
> stack or device, it says to measure or retrieve it. Still needs a
> paired golden and owner review to meet the full Part A3 contract.

Scope: pad probes, caps negotiation, latency tracing.

When to reach for it: A GStreamer pipeline produces no data, wrong data, or unexplained latency.

## Methodology

- Read caps negotiation first: most 'no data' bugs are a caps mismatch at a specific pad, not a dead element. GST_DEBUG at the right categories names the failing boundary.
- Measure latency with buffer PTS at pad probes on each element boundary, not wall-clock around the loop; this localizes the stalling element.
- A not-negotiated or not-linked error names the exact pad; trust it and inspect that junction rather than guessing upstream.
- Use a fakesink/identity with probes to bisect a broken pipeline into a working prefix and the first bad element.

## Common traps

- Adding a convert element to 'fix' caps and silently introducing a copy that dominates latency.
- Blaming a source when the real failure is a downstream caps filter that no upstream format satisfies.

## Definition of done

- Every element boundary negotiates; per-element latency measured via pad probes.
