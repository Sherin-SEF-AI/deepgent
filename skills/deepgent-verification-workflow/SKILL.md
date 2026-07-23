---
name: deepgent-verification-workflow
description: How to take an AV/CV/embedded task from code to verified-on-hardware using deepgent's own gates and evidence artifacts, in the correct order, so "done" means metrics on the target rather than "compiles and tests pass".
---

# deepgent verification workflow

The definition of done is a verified artifact meeting a stated metric on the
target board. This skill sequences deepgent's own tooling to get there. Every
step is a real deepgent command; the facts below are about deepgent itself, not
about any specific silicon.

## Order of operations (cheap and deterministic first)

1. Pre-empt known failures before planning. `deepgent premortem --symptom
   "<task>" --hw <board>` queries the failure corpus and compatibility matrix
   and lists prior failure modes for this hardware/stack, each with its
   verified fix. When you run a task with `deepgent "<task>"`, this is injected
   into the plan automatically (premortem_enabled).
2. Check the design before touching hardware. For a carrier board plus
   peripherals, `deepgent hw-check --config carrier.json` detects pin/mux
   collisions, I2C address clashes, and power-rail overruns from a
   provenance-carrying config. Peripherals lacking datasheet provenance are
   flagged as unverified, never trusted.
3. Build and static-gate. Build inside the pinned toolchain container
   (`deepgent containers build jp6`). C/C++ writes are gated by misra_gate;
   CUDA writes raise a cuda_gate reminder that the dynamic check still owes a
   run.
4. Dynamic safety gate for CUDA. `deepgent cuda-check --board <id> --build
   <cmd> --run <cmd>` runs compute-sanitizer (memcheck/racecheck) on the target
   and fails on any memory or race error. This is the GPU analog of the MISRA
   gate and must pass before a kernel is called done.

## Prove the metric on the target (never on x86)

- Performance envelope, not a burst number: `deepgent profile thermal` reports
  sustained vs burst throughput and the thermal knee across power modes.
  `deepgent profile latency` gives per-stage p50/p95/p99, jitter, and a
  glass-to-glass p99 budget gate. `deepgent profile nsight` classifies the
  dominant bottleneck (compute / memory-copy / sync / CPU) with fixes.
- Accuracy, not just speed: `deepgent accuracy gate --board <id> --command
  <eval> --metric mAP --baseline <b>` runs an on-device eval and fails on
  regression beyond a tolerance. `deepgent accuracy score` computes real VOC
  mAP or top-1 from local predictions plus ground truth.
- Choosing under a budget: `deepgent select-model --manifest models.json
  --max-power 15 --min-fps 30` benchmarks candidates and returns only those
  that provably meet the envelope. `deepgent quant-sweep` sweeps
  precision/batch/device to a Pareto frontier.
- Across a fleet: `deepgent fleet --boards a,b --command <bench>` builds a
  compat+perf matrix and exits nonzero on any regression, emitting
  matrix-claim candidates.
- Behavioral safety of a new model: `deepgent shadow --fixture <bag>
  --incumbent <v1> --candidate <v2>` diffs the two versions frame by frame on
  recorded reality.

## When something fails

- Do not retry blindly. On a tool failure the reflexion_tap hook injects a
  taxonomy-classified, root-cause replan; `deepgent reflect --tool <t> --error
  "<e>"` reproduces it and adds the nearest corpus-verified fix.
- Feed the flywheel: a failed-to-passed transition drafts a corpus tuple
  candidate; verified fleet runs become matrix claims. `deepgent matrix
  analyze` then reasons over those claims (transitive inference, contradiction
  detection, next-cell-to-verify).

## Evidence

Every run writes artifacts under `.deepgent/runs/<id>/` (JSON plus a rendered
report). Cite the run id when claiming a metric; a claim without an artifact is
not verified. Never reuse timing or calibration caches across a `versions.toml`
bump.
