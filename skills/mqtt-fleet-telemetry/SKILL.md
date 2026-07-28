---
name: mqtt-fleet-telemetry
description: store-and-forward, backpressure.
status: methodology-complete
---

# mqtt-fleet-telemetry

> Methodology skill: durable engineering practice, not device facts. It
> asserts no hardware-specific value; where a number depends on your
> stack or device, it says to measure or retrieve it. Still needs a
> paired golden and owner review to meet the full Part A3 contract.

Scope: store-and-forward, backpressure.

When to reach for it: Shipping telemetry from intermittently-connected edge devices.

## Methodology

- Design for the disconnected case first: buffer locally with bounded storage and forward opportunistically; lost telemetry on a dropped link is the default failure to prevent.
- Bound the backpressure: an unbounded local queue turns a network outage into a disk-full outage. Drop or downsample by policy when the buffer fills.
- Choose QoS per topic (0/1/2) against delivery-guarantee vs broker-load tradeoffs, not globally; clean-session and retained-message choices change reconnect behavior.
- Batch and compress buffered messages before forwarding to amortize connection cost on expensive links.

## Common traps

- QoS 2 everywhere, overloading the broker for data that tolerates loss.
- An unbounded offline queue that fills the disk and takes the device down.

## Definition of done

- Telemetry survives a simulated multi-hour outage with bounded local storage and a defined drop policy.
