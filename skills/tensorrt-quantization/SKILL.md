---
name: tensorrt-quantization
description: INT8/FP16 quantization and benchmarking with TensorRT 10.x on Jetson (JetPack 6.x, TRT 10.3), including DLA constraints and trtexec migration traps.
---

# TensorRT quantization on Jetson (TRT 10.x / JetPack 6.x)

Applies to TensorRT 10.x as shipped in JetPack 6.1/6.2 (TRT 10.3, CUDA 12.6,
DLA 3.1, L4T 36.4.x). Every claim below is source-tagged; sources are NVIDIA
documentation retrieved 2026-07-22.

## trtexec flags that changed in TRT 10 (build failures if you use 8.x habits)

- `--workspace=N` is gone; use `--memPoolSize=workspace:<size>` (also sets DLA
  SRAM/local/global pools). [TRT >= 10.0]
  https://docs.nvidia.com/deeplearning/tensorrt/latest/api/migration/tensorrt-8x-to-10x-trtexec.html
- Removed with hard errors: `--batch`, `--maxBatch`, `--deploy`, `--model`,
  `--uff*`, `--output` (implicit batch, Caffe, and UFF are gone entirely),
  `--minTiming` (use `--avgTiming`), `--buildOnly` (use `--skipInference`),
  `--nvtxMode` (use `--profilingVerbosity`), `--heuristic` (use
  `--builderOptimizationLevel=N`). [TRT >= 10.0] (same migration page)
- Deprecated but still working in 10.x: `--streams` -> `--infStreams`,
  `--plugins` -> `--staticPlugins`, `--weightless` -> `--stripWeights`;
  `--profilingVerbosity` values renamed (`default` -> `layer_names_only`,
  `verbose` -> `detailed`). (same migration page)
- `--int8` with no `--calib=<cache>` assigns random dynamic ranges: valid for
  performance measurement only, never for accuracy runs. [TRT 10.x]
  https://docs.nvidia.com/deeplearning/tensorrt/10.x.x/reference/command-line-programs.html
- `--timingCacheFile` entries are only trustworthy on the same
  CUDA/TRT/device/clock configuration; reuse across configs can cause
  functional or performance issues. [TRT 10.x] (command-line reference above)

## API status you must plan around

- Implicit batch is removed in TRT 10.0; everything is explicit batch.
  [TRT >= 10.0]
  https://docs.nvidia.com/deeplearning/tensorrt/10.x.x/getting-started/release-notes-10/10.0.0-ea.html
- `IInt8Calibrator` and all calibrator variants are deprecated in 10.0 and
  removed in TRT 11 along with weak-typing APIs (`setDynamicRange`,
  per-precision builder flags). Calibrator PTQ works on JetPack 6.x but is a
  dead end; plan new work on explicit Q/DQ quantization.
  https://docs.nvidia.com/deeplearning/tensorrt/latest/api/migration/tensorrt-10x-to-11x.html
- NVIDIA's stated direction: use TensorRT Model Optimizer (PTQ and QAT for
  PyTorch/ONNX) to produce explicitly quantized models. For explicit Q/DQ
  networks, do NOT pass precision build flags; they are not required and
  should not be specified. [TRT 10.x]
  https://docs.nvidia.com/deeplearning/tensorrt/10.x.x/inference-library/work-quantized-types.html

## Calibration (while using the deprecated path on TRT 10.3)

- `IInt8EntropyCalibrator2` is the recommended entropy calibrator for CNNs
  and is required for DLA; `IInt8MinMaxCalibrator` suits NLP-style ranges.
  [TRT 10.x] (work-quantized-types page above)
- NVIDIA's dataset guidance: ~500 well-randomized, distribution-matched
  images suffice for ImageNet-class calibration. (same page)
- Calibration caches are portable across devices (calibration happens before
  layer fusion) but NOT across TensorRT releases: an x86-built cache can seed
  an Orin build on the same TRT version, but never survive a JetPack bump.
  (same page)

## DLA on Orin

- DLA supports FP16 and INT8 only. Add `--allowGPUFallback`
  (`BuilderFlag::kGPU_FALLBACK`) or the build fails on any unsupported or
  out-of-range layer. [TRT 10.x]
  https://docs.nvidia.com/deeplearning/tensorrt/10.x.x/inference-library/work-with-dla.html
- Orin DLA FP16 convolutions can be up to 2x slower than Xavier's; NVIDIA
  recommends INT8 on Orin DLA. Managed SRAM defaults to 0.5 MiB per core.
  (same page)
- Version trap: newer standalone TensorRT-for-Jetson drops support Orin iGPU
  only ("Orin DLA will be supported in a future release"); DLA workflows must
  use the JetPack-bundled TRT 10.3 + DLA 3.1.
  https://docs.nvidia.com/deeplearning/tensorrt/10.x.x/getting-started/support-matrix.html
  https://docs.nvidia.com/jetson/archives/jetpack-archived/jetpack-62/release-notes/index.html

## Benchmarking honestly with trtexec

- Defaults: at least 200 ms warmup, then at least 10 iterations or 3 seconds,
  whichever is longer. For exact iteration counts use
  `--warmUp=0 --duration=0 --iterations=N`. [TRT 10.x]
  https://docs.nvidia.com/deeplearning/tensorrt/latest/performance/benchmarking.html
- Reported decomposition: Host Latency = H2D + GPU Compute + D2H; the summary
  prints min/max/mean/median and 90/95/99th percentiles. (same page)
- trtexec p99 is not pipeline p99: random generated inputs (no decode or
  preprocessing), one-batch-ahead enqueueing, optional CUDA graphs
  (`--useCudaGraph`), and idealized clocks. Always re-measure inside the real
  pipeline before claiming a latency budget is met. (same page)

## Golden-task workflow on deepgent

1. Build engines inside the jp6 toolchain container; run and measure only on
   the target board (tegrastats + trtexec percentiles into the run dir).
2. Record the exact TRT version from the board in the run artifacts; never
   reuse timing or calibration caches across versions.toml bumps.
3. For mAP-delta criteria, evaluate accuracy with the deployed engine on the
   board, not with the x86 build.
