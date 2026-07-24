---
name: sensor-latency-tracing
description: Methodology for measuring and reducing glass-to-glass latency in a sensor -> inference -> actuation pipeline - per-stage instrumentation, reading the distribution (p50/p95/p99/jitter), finding the bottleneck, and gating the p99 total against a budget with deepgent. Methodology only; concrete latencies must be measured on the pipeline.
---

# Glass-to-glass latency tracing

Latency is the metric AV pipelines live and die by, and a single mean hides
where time goes and how bad the tail is. Measure end to end (sensor to
actuation), per stage, with the distribution - not one average.

## Instrument per stage, per frame

- Emit a per-frame, per-stage timing from the pipeline. deepgent's contract is
  one line per stage: `STAGE <name> <ms> [frame=<n>]` (or the JSON form). Stages
  are typically capture, ISP/preprocess, inference, post-process, actuation.
- Group by frame to get a per-frame glass-to-glass total; do not sum per-stage
  medians (that hides correlation and the tail).

## Read the distribution, not the mean

- Per stage: p50, p95, p99, min/max, and jitter (standard deviation). The
  bottleneck is the stage with the worst p99, not the worst mean.
- Tail ratio (p99/p50): a high ratio signals scheduling, contention, or GC/GIL
  stalls even when the mean looks fine.
- Gate on the p99 of the per-frame total: `deepgent profile latency --board
  <id> --command <pipeline> --budget-ms <budget>`. It reports per-stage jitter
  and the bottleneck and fails when p99 exceeds the budget.

## Engine latency is not pipeline latency

Standalone engine benchmarks use idealized inputs (no decode/preprocess),
one-batch-ahead enqueue, and fixed clocks. They are a floor, not the deployed
number. Always re-measure inside the real pipeline before claiming a budget is
met.

## Reduce it in the right place

- Copy-bound (host<->device dominates): keep tensors resident on the GPU across
  frames, use pinned memory, overlap copies with compute via streams.
- Sync-bound (stalls dominate): remove unnecessary device syncs; use events and
  async APIs so CPU and GPU overlap.
- Compute-bound (kernels dominate): lower precision or a lighter model; profile
  the top kernel with `deepgent profile nsight`, which classifies the dominant
  bottleneck and lists the matching fix.
- CPU-starved (GPU idle waiting on CPU pre/post): parallelize or offload the CPU
  stages (NVDEC/VPI/DLA); check for single-threaded or GIL bottlenecks.

## Boundary

Per-stage latencies, ISP timings, and actuation delays are properties of the
specific pipeline and hardware. Measure them; do not assert numbers from
memory. Cite the run id for any latency claim.
