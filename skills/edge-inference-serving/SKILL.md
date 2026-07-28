---
name: edge-inference-serving
description: batching, multi-stream scheduling.
status: methodology-complete
---

# edge-inference-serving

> Methodology skill: durable engineering practice, not device facts. It
> asserts no hardware-specific value; where a number depends on your
> stack or device, it says to measure or retrieve it. Still needs a
> paired golden and owner review to meet the full Part A3 contract.

Scope: batching, multi-stream scheduling.

When to reach for it: Serving one or more inference streams on a constrained accelerator.

## Methodology

- Size the batch to the p99 latency budget, not peak throughput; dynamic batching with a max-delay bound trades a little latency for large throughput gains.
- Measure tail latency under concurrent streams, not a single stream in isolation; contention on one accelerator changes the picture entirely.
- Warm the engine and pin/reuse buffers; first-inference and cold-allocation latency are not steady state and must be excluded from SLO measurement (but reported separately).
- Pin each model's precision/engine to the device once; rebuilding or re-planning per request destroys latency.

## Common traps

- Reporting single-stream latency for a multi-stream deployment.
- Unbounded dynamic-batch delay that helps throughput but blows the latency SLO.

## Definition of done

- p99 latency measured under the real concurrent stream count meets the SLO.
- Warm-up excluded from SLO but reported.
