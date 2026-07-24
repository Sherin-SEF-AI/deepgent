---
name: hailo-ai-accelerator
description: Methodology for using a Hailo NPU (Raspberry Pi AI HAT+/AI Kit, Hailo-8/8L) - the compile-to-HEF then run-with-HailoRT flow, model porting and quantization, and measuring on-device with deepgent. Process only; SDK versions, op support, and TOPS figures must come from Hailo's documentation, not memory.
---

# Hailo AI accelerator (AI HAT+ / AI Kit)

A Hailo NPU is a dataflow accelerator attached to a host (Pi 5 over PCIe/M.2).
It does not run arbitrary CUDA/TensorRT; models are compiled ahead of time into
a Hailo executable (HEF) and executed by the HailoRT runtime on the host. Plan
for an offline compile step and a runtime handoff, not a JIT engine build.

## The two-stage flow

1. Compile (offline, on a workstation): take a trained ONNX/TF model, quantize
   it, and compile to a HEF with the Hailo toolchain. Unsupported ops must be
   handled (replaced, or run on the host CPU); the supported op set and the
   compiler are version-specific - read Hailo's docs, do not assume.
2. Run (on the host): load the HEF and stream inference through HailoRT. The Pi
   CPU handles capture/pre/post; the NPU handles the network. This is the same
   copy/sync/compute split as any accelerator (see sensor-latency-tracing).

## Porting a model

- Start from a Hailo-supported architecture family when possible; exotic layers
  are the usual compile blocker.
- Quantize for INT8 with a representative calibration set (same principles as
  int8-calibration-methodology) and validate accuracy after compile, not before
  - the quantized HEF is what runs, so gate its accuracy: `deepgent accuracy
  gate` against the float baseline.
- Keep pre/post-processing off the NPU and off the hot path; a CPU-starved Pi
  will bottleneck the NPU (profile with a per-stage latency trace).

## With deepgent

- Register: `deepgent boards catalog hailo-8-ai-hat` shows the profile; add the
  Pi host with a `hailo` capability.
- Measure on-device: latency via `deepgent profile latency`, sustained behavior
  and thermals via `deepgent soak`; report sustained throughput, not burst.
- Across a fleet: `deepgent fleet` and `deepgent shadow` compare a Hailo build
  against a Jetson build on the same fixture, evidence-based.

## Boundary

TOPS ratings, supported op lists, HailoRT/DFC versions, HAT power draw, and
host compatibility are vendor facts. Retrieve them from Hailo's documentation
(with provenance) or measure on the board; never assert them from memory.
