---
name: power-thermal-tuning
description: Methodology for tuning edge inference under power and thermal limits - sustained vs burst throughput, the thermal knee, energy per inference, DVFS/power modes, and how to profile and gate it with deepgent. Measurement principles only; device-specific power figures must be measured, never asserted.
---

# Power and thermal tuning for edge inference

The deployable number is the sustained one. A fanless enclosure throttles as it
heats, so a short benchmark records a pre-throttle peak that does not hold in
the field. Tune and report against steady state, not burst.

## Measure sustained, find the knee

- Hold a representative workload long enough to reach thermal steady state.
  Compare the first window (burst) to the last (sustained). The thermal knee is
  where the GPU clock throttles and throughput drops.
- Across power modes: `deepgent profile thermal --board <id> --workload <cmd>
  --modes <id:name,...>` reports burst vs sustained fps and the knee per mode,
  and restores the original power mode afterward.
- Report sustained fps as deployable; report burst only as a ceiling.

## Energy per inference, not just watts

- Two configs at equal fps can differ greatly in power. For battery or thermal
  budgets, compare energy per inference (joules per frame), integrated from
  rail power over the run, rather than instantaneous watts.
- `deepgent soak` captures sustained thermals and energy over long runs and
  snapshots the first anomaly (thermal ceiling, dropped samples).

## The tuning levers (measure each, do not assume)

- Power mode / DVFS: lower modes cap clocks and power; the right mode is the one
  that holds the target sustained fps within the thermal budget. Which mode
  that is depends on the board and workload - measure it.
- Precision: INT8/FP16 cut compute energy; validate accuracy with the accuracy
  gate before claiming the win (see int8-calibration-methodology).
- Placement: moving work to DLA or NVDEC/VPI frees the GPU and changes the power
  profile; confirm layer support and re-measure.
- Cooling and enclosure: the same board sustains more with better airflow; the
  thermal knee moves. Treat cooling as part of the measured configuration.

## Gate it

Wire a sustained-fps and a tj-ceiling threshold into the soak/thermal run so a
regression fails the build, not a demo. Record the power mode, cooling, and L4T
version in the run artifacts; a power number without that context is not
reproducible.

## Boundary

Per-board wattage, clock tables, tj limits, and power-mode definitions are
hardware facts. Read them from the board (tegrastats, nvpmodel) or the spec and
cite them; never state a specific figure from memory.
