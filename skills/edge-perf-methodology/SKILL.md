---
name: edge-perf-methodology
description: Measurement methodology for edge inference (sustained vs burst throughput, thermal knee, glass-to-glass latency, tail jitter, energy per inference) so reported numbers reflect real deployment rather than idealized benchmarks. Methodology only; no device-specific values are asserted.
---

# Edge performance measurement methodology

This skill is about *how to measure*, not about any specific board's numbers.
It states measurement principles and maps each to the deepgent tool that
enforces it. Treat any concrete throughput/power figure as unverified until a
run artifact on the actual target proves it.

## Burst is a lie; measure sustained

- A short benchmark on a fanless enclosure records the pre-throttle peak. The
  number that holds in the field is the thermally saturated one.
- Hold the workload long enough to reach steady state and compare the first
  window (burst) to the last window (sustained). The "thermal knee" is where
  the GPU clock throttles and throughput drops. deepgent: `profile thermal`
  reports burst vs sustained fps and the knee across power modes, and restores
  the original power mode afterward.
- Report the sustained figure as the deployable one; report burst only as a
  ceiling.

## Latency: glass-to-glass, per stage, with the tail

- End-to-end (sensor to actuation) is the metric that matters; a single mean
  hides where time goes and how bad the tail is.
- Measure per stage and summarize the distribution: p50, p95, p99, min/max, and
  jitter (standard deviation). The bottleneck is the stage with the worst p99,
  not the worst mean. A high p99/p50 tail ratio signals scheduling or
  contention problems even when the mean looks fine.
- Gate on p99 of the per-frame total, not on p50. deepgent: `profile latency`
  parses per-frame per-stage timings and gates the glass-to-glass p99 against a
  budget, reporting per-stage jitter and the bottleneck.
- Engine benchmarks (idealized inputs, one-ahead enqueue, fixed clocks) are not
  pipeline latency. Always re-measure inside the real pipeline before claiming a
  budget is met.

## Find the cause before optimizing

- fps tells you it is slow; it does not tell you why. Classify the dominant
  time sink first: compute-bound, host<->device copy-bound, sync-stall-bound,
  or CPU-starved. Each has a different fix (lower precision vs keep tensors
  resident vs remove synchronizes vs move pre/post off the hot path).
- deepgent: `profile nsight` classifies the bottleneck from a normalized
  device-time summary and lists the matching mitigations.

## Power and energy, not just speed

- Two configs at the same fps can differ greatly in power. For battery or
  thermal budgets, compare energy per inference (joules per frame), integrated
  from rail power over the run, not instantaneous watts.
- Constrain selection by the real envelope (<=W, >=fps, optionally accuracy)
  and let measured evidence decide. deepgent: `select-model` and `quant-sweep`
  filter/rank by measured latency, fps, power, and accuracy; the soak harness
  captures sustained thermals and energy over long runs.

## Accuracy is half of done

- Quantization and pruning are unsafe without an accuracy check. Measure the
  metric (mAP, top-1) on-device against a pinned baseline and gate on
  regression beyond a stated tolerance. Speed with an unmeasured accuracy drop
  is not a win. deepgent: `accuracy gate` and `accuracy score`.

## Reproducibility

- Record the exact stack (L4T, CUDA, TensorRT) from the board in the run
  artifacts. Do not reuse timing or calibration caches across version bumps.
  Every claim cites a run id.
