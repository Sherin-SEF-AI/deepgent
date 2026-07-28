---
name: v4l2-subdev-drivers
description: V4L2 subdev drivers. DRAFT methodology pack, unreviewed, no paired golden.
tier: T1
status: draft-unreviewed
---

# v4l2-subdev-drivers (draft, unreviewed)

> Status: DRAFT. Not owner-reviewed and has no paired golden, so it does
> not yet meet the Part A3 skill contract. Methodology only: every
> device-specific value below is deliberately deferred to retrieval or
> on-hardware measurement, never asserted from memory (CLAUDE.md s1, s23).

Scope: V4L2 subdev drivers.

## Methodology and traps

- A subdev exposes formats and controls through the media API; get_fmt/set_fmt and enum_mbus_code must reflect real sensor modes, not a hardcoded one.
- Controls (exposure, gain) belong on the subdev; putting them on the video node breaks tools that walk the graph.
- Streaming start/stop ordering across the pipeline is a frequent bug source; follow the s_stream contract exactly.
- Return real errors from probe; a driver that probes green but produces no frames wastes days.

## Retrieve or verify (do not assume)

- the sensor register sequences behind each advertised mode (with provenance).
- the control ranges and default values from the sensor datasheet.

## Before this becomes a real skill

- Pair it with a golden that fails or exceeds loop budget without it.
- Replace each 'retrieve or verify' item with a provenance-carried fact.
- Owner line-by-line review.
