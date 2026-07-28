---
name: jetson-power-thermal
description: nvpmodel, jetson_clocks, DVFS, thermal zones. DRAFT methodology pack, unreviewed, no paired golden.
applies_to: JetPack 6.x / L4T r36.x
tier: T0
status: draft-unreviewed
---

# jetson-power-thermal (draft, unreviewed)

> Status: DRAFT. Not owner-reviewed and has no paired golden, so it does
> not yet meet the Part A3 skill contract. Methodology only: every
> device-specific value below is deliberately deferred to retrieval or
> on-hardware measurement, never asserted from memory (CLAUDE.md s1, s23).

Scope: nvpmodel, jetson_clocks, DVFS, thermal zones.

## Methodology and traps

- Pin the power mode before every benchmark: an unpinned nvpmodel makes fps and latency non-reproducible run to run.
- jetson_clocks locks clocks to max but disables DVFS; report both jetson_clocks-on (ceiling) and default (deployment) numbers, never just the ceiling.
- Thermal throttling appears as a slow fps decay minutes into a run, not at start: hold the workload past the thermal knee before trusting a number.
- Read thermal zones and rail power from sysfs/tegrastats, not from a one-shot sample; use a windowed mean and the max.
- A fan curve change silently shifts the sustained-vs-burst gap; record the cooling configuration with every result.

## Retrieve or verify (do not assume)

- nvpmodel mode table and per-mode clock/power caps for the specific module (retrieve or read on device).
- thermal-zone names and Tj throttle thresholds for the module.
- which tegrastats fields exist on this L4T release (the format changes between releases).

## Before this becomes a real skill

- Pair it with a golden that fails or exceeds loop budget without it.
- Replace each 'retrieve or verify' item with a provenance-carried fact.
- Owner line-by-line review.
