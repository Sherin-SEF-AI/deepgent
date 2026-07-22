# Golden tasks and evals

Migrated from CLAUDE.md section 17 after Phase 0.

Golden task YAML schema:

```yaml
id: gt-0007
title: INT8 quantize yolo detector within 1pt mAP
class: perception/quantization
board: agx-orin
skills: [tensorrt-quantization]
inputs: { model: fixtures/y11m.onnx, calib: fixtures/calib_256/ }
success:
  - metric: map50_95_delta, op: ">=", value: -1.0
  - metric: p99_latency_ms, op: "<=", value: 25
  - metric: loop_count, op: "<=", value: 6
budget_usd: 1.50
timeout_min: 30
```

- Launch target: 25 goldens across bring-up, quantization, pipelines, drivers,
  debugging. Each scored mechanically; no LLM-judged goldens.
- Regression gate: CI blocks merge if any previously passing golden fails or
  aggregate cost/loop-count regresses >15% without a justification label.
- Long-horizon ambition (Phase 5+): publish a public subset as BringupBench.

## Implementation notes (Phase 0)

- Schema and mechanical scorer live in `src/deepgent/evals/schema.py`; golden
  YAMLs live in `golden/<id>.yaml`; run artifacts in `.deepgent/runs/<id>-<ts>/`
  (metrics.json, result.json, raw captures).
- Deterministic implementations are registered per task class in
  `src/deepgent/evals/runner.py`; gt-0001 (`bringup/cuda-smoke`) is the first.
  Agent-driven goldens arrive with the board-farm MCP in Phase 2.
