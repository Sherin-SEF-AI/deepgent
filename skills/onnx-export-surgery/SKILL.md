---
name: onnx-export-surgery
description: opsets, dynamic shapes, graph edits.
status: methodology-complete
---

# onnx-export-surgery

> Methodology skill: durable engineering practice, not device facts. It
> asserts no hardware-specific value; where a number depends on your
> stack or device, it says to measure or retrieve it. Still needs a
> paired golden and owner review to meet the full Part A3 contract.

Scope: opsets, dynamic shapes, graph edits.

When to reach for it: Exporting a trained model to a runtime and fixing graph-level export issues.

## Methodology

- Pin the opset to what the target runtime supports (check the runtime's op/opset matrix); a newer opset exports cleanly and fails at load or falls back to slow paths.
- Declare dynamic axes at export time; you cannot make a static-shape ONNX dynamic afterward without re-export.
- After any graph edit (constant folding, node fusion, shape inference, opset conversion), verify numerics against a reference input with a tight tolerance; folds can silently change outputs.
- Strip training-only subgraphs (dropout, aux heads, loss) before export; they bloat the graph and can trip the runtime.
- Simplify with a graph optimizer, but re-verify after; aggressive fusion occasionally changes semantics for custom ops.

## Common traps

- Exporting with a batch dimension hardcoded when the deployment batches dynamically.
- Assuming an op exists in the target runtime because it exists in the framework; check the support matrix.

## Definition of done

- Exported model loads on the target runtime at the pinned opset and matches the reference output within tolerance.
- Dynamic axes declared to match deployment batching/resolution.
