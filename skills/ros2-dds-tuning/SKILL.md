---
name: ros2-dds-tuning
description: Cyclone/Fast DDS, discovery, shared memory. DRAFT methodology pack, unreviewed, no paired golden.
applies_to: ROS 2 Humble/Jazzy
tier: T1
status: draft-unreviewed
---

# ros2-dds-tuning (draft, unreviewed)

> Status: DRAFT. Not owner-reviewed and has no paired golden, so it does
> not yet meet the Part A3 skill contract. Methodology only: every
> device-specific value below is deliberately deferred to retrieval or
> on-hardware measurement, never asserted from memory (CLAUDE.md s1, s23).

Scope: Cyclone/Fast DDS, discovery, shared memory.

## Methodology and traps

- Discovery scales badly on large graphs; use a discovery server or partition domains rather than flat multicast.
- Shared-memory transport needs matching config on both endpoints; a one-sided setting falls back to network silently.
- QoS incompatibility drops the connection with no data and no obvious error; check reliability/durability/history match first.
- Cyclone and Fast DDS have different tuning knobs and defaults; pick one per deployment and document the XML.

## Retrieve or verify (do not assume)

- the DDS vendor and version deployed, and its shared-memory prerequisites.
- the interface/multicast configuration allowed on the target network.

## Before this becomes a real skill

- Pair it with a golden that fails or exceeds loop budget without it.
- Replace each 'retrieve or verify' item with a provenance-carried fact.
- Owner line-by-line review.
