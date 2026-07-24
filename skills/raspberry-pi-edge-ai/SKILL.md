---
name: raspberry-pi-edge-ai
description: Methodology for edge AI on Raspberry Pi (Pi 5/4/CM) - no CUDA, so offload inference to an attached NPU (Hailo AI HAT, Coral) or run quantized CPU models, with camera via libcamera/CSI and I/O via GPIO. Process and tool mapping; model/OS/interface specifics must be read from the datasheet or the board.
---

# Edge AI on Raspberry Pi

A Raspberry Pi is a CPU-class Linux host, not a CUDA device. Plan accordingly:
the GPU is not a general compute accelerator, so real-time inference either runs
quantized on the CPU or, better, offloads to an attached NPU. Do not assume
CUDA/TensorRT tooling; the toolchain family is Raspberry Pi OS / Debian.

## Choose the compute path first

- CPU-only: quantized (INT8) models via a runtime like ONNX Runtime or
  TFLite/XNNPACK. Viable for light models and low frame rates; measure it, do
  not assume a target fps.
- NPU offload (recommended for real-time): a Hailo AI HAT+/AI Kit (Hailo NPU
  over PCIe/M.2 on Pi 5) or a Coral Edge TPU (USB). Inference moves off the CPU;
  see the hailo-ai-accelerator skill for the compile/run flow.
- The right path depends on model size and fps target on the specific Pi model;
  benchmark on the board, do not extrapolate from a datasheet.

## Camera and I/O

- Camera: the modern stack is libcamera; a CSI camera module attaches to the
  Pi's CSI connector. Confirm the exact module, its libcamera support, and the
  connector/overlay from the module and Pi datasheets; do not assert pin or
  overlay names from memory.
- GPIO/I2C/SPI for sensors and actuators: available but model-dependent in
  routing. Validate a peripheral design with `deepgent hw-check --config
  carrier.json` (pin/I2C/power conflicts) before wiring.

## Register the board with deepgent

- `deepgent boards catalog --family raspberry-pi` lists the known Pi types and
  their categorical profiles; `deepgent boards catalog raspberry-pi-5` shows one
  with the capabilities to consider and what to verify.
- Add it: `deepgent boards add <id> --host <ip> --user <u> --key <path> --type
  raspberry-pi-5 --capabilities gpio,csi`. A Pi + AI HAT should also carry the
  `hailo` capability.

## Measure and gate

- Metrics capture on a non-Jetson target degrades gracefully (no tegrastats);
  drive throughput/latency from the workload's own output.
- Latency: instrument the pipeline and run `deepgent profile latency` for the
  glass-to-glass p99 and bottleneck.
- Sustained health under load and heat: `deepgent soak`. The Pi throttles too;
  report sustained, not burst (see power-thermal-tuning).

## Boundary

RAM, exact interface routing, supported OS images, PCIe lane availability, and
thermal limits vary by Pi model and revision. Read them from the Raspberry Pi
datasheet or the board; never state a specific figure from memory.
