---
name: cuda-kernel-safety
description: Methodology for writing and validating custom CUDA kernels safely on Jetson - the bug classes that matter, how to gate them with compute-sanitizer (memcheck/racecheck/synccheck/initcheck), and how to wire the dynamic check into deepgent's verification loop. Methodology and tool mapping; no device-specific numbers asserted.
---

# CUDA kernel safety

A kernel that "runs and gives plausible output" can still be corrupt: races
and out-of-bounds accesses often produce wrong results only under specific
timing or input sizes. Treat a custom kernel as unverified until it passes a
dynamic sanitizer on the target. compute-sanitizer is the GPU analog of the
MISRA gate: dynamic, so it needs a GPU and a compiled binary, and it runs in
the verify/hardware step, not on the dev host.

## Bug classes the sanitizer catches (and why they hide)

- Out-of-bounds / misaligned global or shared access: reads past a buffer, bad
  index arithmetic, wrong stride. Often silent because it hits adjacent valid
  memory. Tool: `--tool memcheck`.
- Data races: two threads write the same location (or read+write) without
  synchronization; shared-memory races across a `__syncthreads()`. Result
  depends on scheduling, so it passes intermittently. Tool: `--tool racecheck`.
- Barrier divergence / illegal `__syncthreads()` under divergent control flow.
  Tool: `--tool synccheck`.
- Use of uninitialized device memory. Tool: `--tool initcheck`.

## The gate

Run `deepgent cuda-check --board <id> --build <cmd> --run <cmd> --tools
memcheck,racecheck`. It builds, runs each tool on the target, parses the
reports into structured errors, and fails on any. A kernel is not "done" until
this is clean. The cuda_gate hook also raises a reminder on every `.cu/.cuh`
write that this dynamic check still owes a run.

## Writing kernels to pass the first time

- Bounds-check every global index against the launch dimensions; never assume
  gridDim*blockDim divides the problem size evenly - guard the tail.
- Guard shared-memory usage with `__syncthreads()` on both sides of a
  read-after-write across threads; never call `__syncthreads()` inside
  divergent branches.
- Initialize device buffers (cudaMemset or an init kernel) before first read;
  do not rely on zeroed memory.
- Keep the failing input small and deterministic so the sanitizer report and
  the fix are reproducible.

## Reproducibility

Sanitizer results are tied to the CUDA/driver/device configuration on the
board. Re-run cuda-check after any `versions.toml` bump; do not carry a clean
result across a toolchain change. Cite the run id when claiming a kernel is
memory- and race-clean.

## What this skill does not assert

Occupancy numbers, register limits, shared-memory sizes, and warp scheduler
behavior are architecture-specific. Retrieve them from the target's spec or
measure with Nsight (`deepgent profile nsight`); do not state them from memory.
