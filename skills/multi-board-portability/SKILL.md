---
name: multi-board-portability
description: Methodology for making one artifact run across a heterogeneous fleet (Jetson + Raspberry Pi + Hailo/Coral), and choosing the right target per workload, using deepgent's fleet matrix, differential, shadow, and compatibility-matrix tools. Process only; per-board specs and support are verified on the board.
---

# Multi-board portability

Different targets are different compute models, not just different clock
speeds: Jetson is CUDA/TensorRT with an integrated GPU (and often DLA); a
Raspberry Pi is CPU-class; a Pi + Hailo/Coral offloads to an NPU via an
ahead-of-time compiled model. A single binary rarely spans all three - design
the artifact as a portable pipeline with a swappable inference backend.

## Design for portability

- Isolate the inference backend behind an interface: TensorRT engine on Jetson,
  HailoRT/HEF on a Hailo target, TFLite/ONNX-Runtime on CPU. The capture,
  pre/post, and control logic stay shared.
- Keep the metric contract identical across backends (the STAGE latency lines,
  the METRIC accuracy line) so the same deepgent gates apply everywhere.
- Version the stack per target (L4T on Jetson, OS image on Pi, HailoRT on the
  accelerator); a build is only valid for the stack it was verified on.

## Verify across the fleet with evidence

- Compatibility + performance matrix: `deepgent fleet --boards a,b,c --command
  <bench>` runs the same benchmark across the fleet, builds a compat+perf matrix
  (which boards pass, and their latency/fps/power), names the fastest passing
  board, and emits matrix-claim candidates. It gates in CI on any regression.
- Head-to-head on one artifact: `deepgent differential` reports the per-metric
  winner (fastest, lowest power, most efficient, cheapest) so board selection is
  measured, not assumed.
- Behavioral equivalence: `deepgent shadow` diffs two backends on the same
  recorded fixture - where do the Jetson and Hailo builds disagree, and by how
  much.

## Choose the target per workload

- Reason over verified claims: `deepgent matrix analyze` does transitive
  inference across compatible stack versions, flags contradictions, and picks
  the highest-value unverified cell to test next. Selection is driven by the
  claims the fleet produced, not by datasheet extrapolation.
- Under a constraint (<=W, >=fps, accuracy): `deepgent select-model` and
  `quant-sweep` return only options that provably meet it, per target.

## Boundary

Which target actually meets a given fps/power/accuracy target is a measured
fact, not a spec-sheet deduction. Run the fleet and cite the run ids; never
declare a board "fast enough" from memory.
