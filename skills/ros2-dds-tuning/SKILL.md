---
name: ros2-dds-tuning
description: Cyclone/Fast DDS, discovery, shared memory.
applies_to: ROS 2 Humble/Jazzy
status: methodology-complete
---

# ros2-dds-tuning

> Methodology skill: durable engineering practice, not device facts. It
> asserts no hardware-specific value; where a number depends on your
> stack or device, it says to measure or retrieve it. Still needs a
> paired golden and owner review to meet the full Part A3 contract.

Scope: Cyclone/Fast DDS, discovery, shared memory.

When to reach for it: A ROS 2 graph has discovery storms, dropped topics, or high inter-process latency.

## Methodology

- QoS incompatibility drops a connection with no data and no obvious error; check reliability, durability, and history compatibility between pub and sub first.
- Discovery scales badly on large flat graphs; use a discovery server or partition into domains rather than relying on flat multicast.
- Shared-memory transport needs matching configuration on both endpoints; a one-sided setting silently falls back to the network loopback.
- Cyclone and Fast DDS expose different knobs and defaults; choose one per deployment and version its XML config with the code.

## Common traps

- A reliable subscriber and best-effort publisher that never connect, debugged as a code bug.
- Assuming intra-host comms use shared memory when only one side enabled it.

## Definition of done

- QoS profiles compatible across every pub/sub pair; discovery and transport configured and versioned.
