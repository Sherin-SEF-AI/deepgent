---
name: int8-calibration-methodology
description: Methodology for INT8 quantization on edge - designing the calibration set, choosing PTQ vs QAT vs explicit Q/DQ conceptually, validating accuracy against a baseline before shipping, and detecting when recalibration is needed. Process only; TRT-specific API details live in the tensorrt-quantization skill and must carry sources.
---

# INT8 calibration methodology

Quantization is a speed-for-accuracy trade, and it is unsafe without an
accuracy check. The rule: never ship an INT8 engine on the strength of its fps
alone. Measure the metric (mAP, top-1) on-device against the FP16/FP32 baseline
and gate on regression. Speed with an unmeasured accuracy drop is not a win.

## The calibration set is the whole game (PTQ)

- Representativeness beats size. The calibration images must match the
  deployment distribution - same lighting, resolution, scene content. A
  calibration set drawn from a different distribution silently degrades
  accuracy on the real input.
- Randomize and de-duplicate. Ordered or near-duplicate frames bias the
  dynamic-range estimates.
- Version it. The calibration set is an input to the artifact; record which set
  produced which engine so a result is reproducible.

## PTQ vs QAT vs explicit Q/DQ (choose by accuracy headroom)

- Post-training quantization (PTQ) with a calibrator is the fast path: no
  retraining, minutes to calibrate. Use it first and measure the drop.
- If PTQ loses too much accuracy, quantization-aware training (QAT) or an
  explicitly quantized (Q/DQ) model recovers most of it at the cost of a
  training loop. Prefer explicit Q/DQ for new work; the toolchain direction is
  toward explicit quantization.
- For DLA targets, INT8 is often the recommended precision; confirm layer
  support and plan a GPU fallback for unsupported layers.

## Validate before you trust

1. Build FP16 and INT8 engines from the same model on the target.
2. Score both on-device against a labeled validation set:
   `deepgent accuracy gate --board <id> --command <eval> --metric mAP
   --baseline <fp16_mAP> --tolerance <delta>`. It fails on regression beyond
   the tolerance.
3. Explore the trade space with `deepgent quant-sweep` (precision x batch x
   device) to a Pareto frontier; pick with `select-model` under a power/fps
   budget. Speed and accuracy are decided together, from measured evidence.

## Recalibration triggers

- Input distribution shift in the field (new camera, new environment): the old
  dynamic ranges no longer fit. Re-calibrate and re-gate.
- Any model, TensorRT, or JetPack version change. Calibration caches do not
  survive a toolchain release; never reuse one across a `versions.toml` bump.

## Boundary

Exact TensorRT calibrator classes, flags, and API status are version-specific
facts - see the tensorrt-quantization skill, which carries sources. Do not
restate them from memory here.
