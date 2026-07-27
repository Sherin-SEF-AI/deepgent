# deepgent expansion spec + building prompt

Companion to CLAUDE.md. Part A is the design. Part B is the prompt you paste
into Claude Code to build it. Read Part C before you start; it contains the
rules that keep this from collapsing under its own weight.

---

# PART A: THE DESIGN

## A1. Agent roster (14)

Five core agents from CLAUDE.md section 8, plus nine specialists. Specialists
are loaded on demand by task class, never all at once.

### Core (always available)

| Agent | Owns | Exclusive tools | Model tier |
|---|---|---|---|
| architect | plans, interfaces, acceptance criteria, tradeoff analysis | knowledge MCPs (read) | opus |
| implementer | code synthesis, generator invocation | Write, Edit, generators MCP | sonnet |
| verifier | container builds, static analysis, tests | containerized Bash | sonnet |
| hardware-runner | deploy, execute, measure, restore board state | board-farm MCP | sonnet |
| researcher | ALL knowledge queries, provenance enforcement | rag/matrix/corpus MCPs, WebSearch | haiku/sonnet |

### Specialists (loaded by task class)

| Agent | Task classes | Owns |
|---|---|---|
| perception-engineer | training, quantization, accuracy | dataset handling, training loops, PTQ/QAT, accuracy-vs-latency tradeoffs, export surgery |
| driver-engineer | drivers, bringup, kernel | V4L2/I2C/SPI drivers, device tree, kernel modules, SerDes link config |
| pipeline-engineer | pipelines, streaming | DeepStream/GStreamer graphs, ROS 2 node graphs, zero-copy paths, QoS |
| profiler | perf, optimization | nsys/ncu, tegrastats, bottleneck attribution, power-per-inference |
| triage | debugging, incidents | corpus-first failure diagnosis, log/dmesg/crash analysis, repro construction |
| safety-auditor | any C/C++ change, safety review | MISRA-oriented review, static analysis triage, failure mode enumeration |
| data-engineer | datasets, labeling | curation, dedup, splits, calibration sets, auto-label QA |
| integrator | release, deploy, fleet | packaging, OTA, versioning, rollback, staged rollout |
| critic | every non-trivial task, final gate | adversarial diff audit against the capability inventory; can fail a task |

### Delegation contract (enforced, not suggested)

- Subagent contexts are blank. Every delegation prompt carries: task statement,
  approved plan reference, file paths, target metrics, prior failure context,
  and the skills to load. Nothing is assumed shared.
- Tool exclusivity is a hard boundary: only researcher queries knowledge, only
  hardware-runner touches boards, only verifier runs builds. Violations are
  blocked by a PreToolUse hook, not by convention.
- critic runs last on every task with risk tier >= 2 and has veto authority.
  A task cannot report success over a critic failure.
- Max delegation depth 2. Specialists do not spawn specialists.

## A2. Capability layers (10)

Beyond CLAUDE.md sections 3 and 15. Each is a command surface plus the
machinery behind it.

**L1. Corpus-first triage** (`deepgent triage`)
Symptom + logs hit the deterministic corpus search before any model call.
Ranked verified resolutions with provenance. LLM reasoning only on corpus miss.
Every resolution outcome writes back a corpus tuple. This is the flywheel's
consumption end.

**L2. Endurance and thermal** (`deepgent soak`)
Multi-hour runs with thermal profiles, anomaly snapshotting (logs window,
tegrastats, core dumps, frame timing histogram), survival report, automatic
degradation curves. Detects the failures that only appear after hour six.

**L3. Power and efficiency** (`deepgent power`)
Energy per inference from tegrastats rails, later external INA sensors.
Perf-per-watt regression gates alongside latency gates.

**L4. Record and replay** (`deepgent record` / `replay`)
Capture real sensor streams on target, store as content-addressed fixtures,
replay deterministically. Perception regressions get tested against captured
reality without a vehicle. Highest daily-use potential on this list.

**L5. Differential execution** (`deepgent diff-run`)
Same artifact across multiple board types in one command. Table of latency,
accuracy, power, thermal, cost. Hardware selection by evidence.

**L6. Bisection** (`deepgent bisect`)
On any golden regression, auto-bisect across commits and container versions,
on hardware, to the exact breaking change. Upgrade fear becomes a procedure.

**L7. Upgrade impact** (`deepgent upgrade-check`)
Proposed version move in, verified impact report out, built from the matrix
plus a targeted golden run. The single most demanded artifact in Jetson-land.

**L8. Sweep and search** (`deepgent sweep`)
Parameterized grids across the board farm with lease-aware scheduling,
early stopping on dominated configs, ranked results, full provenance.

**L9. Scaffolding generators** (`deepgent scaffold`)
Datasheet-grounded generation: V4L2 driver skeleton + device tree fragment,
ROS 2 package, DeepStream pipeline, TensorRT build harness, Zephyr driver.
Deterministic templates parameterized by RAG-retrieved facts, model fills only
the synthesis gaps.

**L10. Fleet incident intake** (`deepgent watch`)
Telemetry from deployed devices triggers auto-triage: pull logs, reproduce on
farm, propose fix, human approves. Connects the tool to real operational pain.

Cross-cutting, applies to all ten: cost governor with hard caps, full artifact
provenance (every result traceable to run, commit, container digest, board),
resumable long operations, and structured JSON output for every command.

## A3. Skill catalog (65)

Tiers: **T0** build in Phase 1. **T1** build when a golden in that class fails
without it. **T2** build on repeated corpus evidence. **T3** aspirational,
build only if the product goes commercial in that direction.

### Jetson platform (8)
| # | Skill | Tier |
|---|---|---|
| 1 | jetson-bringup | T0 |
| 2 | jetson-power-thermal (nvpmodel, jetson_clocks, DVFS, thermal zones) | T0 |
| 3 | jetson-device-tree (pinmux, overlays, dtb build/flash) | T1 |
| 4 | jetson-boot-flashing (initrd flash, UEFI, A/B rootfs, massflash) | T1 |
| 5 | jetson-multimedia-api (libargus, NvBufSurface, EGL interop) | T1 |
| 6 | l4t-kernel-modules (out-of-tree builds, headers, signing) | T1 |
| 7 | jetson-storage-boot-media (NVMe boot, eMMC, SD) | T2 |
| 8 | jetson-security (secure boot, fuses, disk encryption) | T3 |

### Camera bring-up (7)
| # | Skill | Tier |
|---|---|---|
| 9 | camera-bringup-csi-mipi | T0 |
| 10 | camera-bringup-gmsl2 (SerDes link config order, link-lock debug) | T1 |
| 11 | camera-bringup-fpdlink | T2 |
| 12 | v4l2-subdev-drivers | T1 |
| 13 | isp-tuning (AE/AWB, tuning files, HDR modes) | T2 |
| 14 | camera-sync-trigger (hardware trigger, PTP, PPS alignment) | T1 |
| 15 | usb-gige-cameras (UVC, GenICam, Aravis) | T2 |

### Other sensors (6)
| # | Skill | Tier |
|---|---|---|
| 16 | lidar-integration (packet parsing, driver tuning, motion distortion) | T1 |
| 17 | radar-integration (mmWave config, CAN/Ethernet radar) | T2 |
| 18 | imu-integration (Allan variance, bias, temperature drift) | T1 |
| 19 | gnss-rtk (NTRIP, fix quality, UBX/NMEA) | T2 |
| 20 | wheel-odometry-encoders | T2 |
| 21 | time-sync-ptp (gPTP, chrony, hardware timestamping) | T1 |

### Buses and protocols (6)
| # | Skill | Tier |
|---|---|---|
| 22 | can-bus (SocketCAN, CAN-FD, bitrate/sample point, bus-off recovery) | T0 |
| 23 | automotive-uds-obd (UDS services, DoIP) | T2 |
| 24 | automotive-ethernet (100BASE-T1, SOME/IP, TSN/AVB) | T3 |
| 25 | serial-spi-i2c-debug (analyzer-driven reasoning, clock stretching) | T1 |
| 26 | ros2-dds-tuning (Cyclone/Fast DDS, discovery, shared memory) | T1 |
| 27 | mqtt-fleet-telemetry (store-and-forward, backpressure) | T2 |

### Perception and training (9)
| # | Skill | Tier |
|---|---|---|
| 28 | training-pipelines (dataloaders, AMP, schedulers, reproducibility) | T0 |
| 29 | detection-architectures (YOLO family, DETR, anchor-free tradeoffs) | T1 |
| 30 | segmentation-depth (semantic/instance, mono/stereo depth) | T2 |
| 31 | multi-object-tracking (ByteTrack/BoT-SORT, ReID, association tuning) | T1 |
| 32 | bev-occupancy (LSS/BEVFormer family, multi-cam to BEV) | T2 |
| 33 | dataset-curation (dedup, mining, splits, leakage prevention) | T1 |
| 34 | auto-labeling (SAM-class, pseudo-labels, QA loops) | T2 |
| 35 | cv-eval-metrics (mAP variants, HOTA/MOTA, calibration curves) | T1 |
| 36 | domain-adaptation (night, rain, regional traffic distributions) | T2 |

### Inference optimization (8)
| # | Skill | Tier |
|---|---|---|
| 37 | onnx-export-surgery (opsets, dynamic shapes, graph edits) | T0 |
| 38 | tensorrt-quantization (INT8 PTQ/QAT, calibration, mixed precision) | T0 |
| 39 | tensorrt-plugins (custom layers, plugin registry, versioning) | T2 |
| 40 | deepstream-pipelines (nvinfer, tracker, tiler, zero-copy rules) | T1 |
| 41 | gstreamer-debugging (pad probes, caps negotiation, latency tracing) | T1 |
| 42 | hailo-toolchain (DFC, HEF compile, quantization, model zoo) | T1 |
| 43 | cuda-kernel-optimization (coalescing, occupancy, streams) | T2 |
| 44 | edge-inference-serving (batching, multi-stream scheduling) | T2 |

### Robotics and AV stack (7)
| # | Skill | Tier |
|---|---|---|
| 45 | ros2-systems (lifecycle, composition, launch, params) | T0 |
| 46 | sensor-fusion-estimation (EKF/UKF/ESKF, robot_localization) | T1 |
| 47 | slam-localization (LIO-SAM family, map management, drift) | T2 |
| 48 | planning-control (MPC, pure pursuit, Stanley, lat/long) | T2 |
| 49 | vehicle-interface (drive-by-wire, actuation limits, e-stop design) | T2 |
| 50 | calibration-extrinsics (cam-lidar, cam-imu, targetless) | T1 |
| 51 | simulation-carla (scenarios, sensor models, sim2real gap) | T3 |

### Embedded and firmware (7)
| # | Skill | Tier |
|---|---|---|
| 52 | embedded-c-safety (MISRA-oriented patterns, own words only) | T0 |
| 53 | rtos-zephyr (device model, threading, power management) | T2 |
| 54 | esp-idf (partitions, WiFi/BLE, OTA) | T2 |
| 55 | stm32-baremetal (HAL vs LL, DMA, clock tree) | T2 |
| 56 | bootloaders-ota (A/B updates, rollback, signing) | T2 |
| 57 | low-power-design (sleep modes, wake sources, budgets) | T2 |
| 58 | firmware-debugging (JTAG/SWD, hard fault analysis, tracing) | T2 |

### Systems and production (7)
| # | Skill | Tier |
|---|---|---|
| 59 | linux-realtime (PREEMPT_RT, isolation, affinity, priorities) | T1 |
| 60 | profiling-nsight (nsys/ncu timelines, bottleneck attribution) | T1 |
| 61 | memory-debugging (ASAN/valgrind on edge, leak hunting) | T1 |
| 62 | containerization-edge (GPU passthrough, image size, runtime) | T1 |
| 63 | fleet-deployment (OTA, staged rollout, rollback criteria) | T2 |
| 64 | observability-edge (metrics, log shipping, crash dumps) | T2 |
| 65 | functional-safety-process (26262/21448 workflow, own words only) | T3 |

Tier counts: T0 = 11, T1 = 24, T2 = 25, T3 = 5.

### Skill quality contract (applies to all 65)

Every skill must:
- earn its context: at least one golden that fails or exceeds loop budget
  without it, and passes with it. No golden, no merge. No exceptions.
- carry version applicability (`applies_to` in frontmatter: L4T range,
  TensorRT range, ROS distro) and source provenance per claim.
- contain only non-obvious durable knowledge. Anything the base model already
  knows is deleted, not kept "for completeness".
- keep SKILL.md under 150 lines with detail in `references/` loaded on demand.
- contain zero licensed standards text. MISRA and ISO content is described in
  own words and enforced by tooling.
- be reviewed line by line by the owner. An unreviewed skill is a liability,
  not an asset: it teaches the agent to be confidently wrong.

---

# PART B: THE BUILDING PROMPT

Paste into Claude Code from inside the deepgent repo, after Phase 0 is green.

```
Read CLAUDE.md fully, then read docs/expansion.md (this design).

GOAL
Extend deepgent from the Phase 0 core to the full architecture: 14 agents,
10 capability layers, and the 65-skill catalog with tier gates. Nothing here
is a prototype. Every delivered item is production-grade per CLAUDE.md
sections 1, 5, 6, and 23.

EXECUTION MODEL
- One work order per session. Stop for my review between work orders.
- Never start a work order before the previous one is merged and green.
- For every work order, apply the FULL-CAPABILITY protocol below in full.
- Clear context between work orders.

FULL-CAPABILITY PROTOCOL (mandatory per work order)

Step 1 - Capability inventory, before any code.
  Numbered checklist covering: all behaviors and modes; every CLI flag,
  option and config key with defaults; every failure mode and the exact
  user-facing message; concurrency, timeouts, retries, cancellation,
  resume; limits and behavior at each limit; telemetry events emitted;
  auth, secrets, and input validation. Mark v3-grade items [ADV].
  STOP and wait for my approval. The approved inventory is the definition
  of done: everything on it, nothing outside it.

Step 2 - Implementation.
  No stubs, placeholders, mock data, simulated results, TODO/FIXME,
  NotImplementedError, silent fallbacks, or "basic for now". Every branch
  reachable and tested. If an item cannot be completed (missing hardware,
  missing API), STOP and report the blocker rather than faking it.

Step 3 - Verification.
  A test per inventory item including every failure path, asserting exact
  error messages and exit codes. Integration tests through the real
  container or board path where applicable. ruff, mypy --strict, and
  pytest -m "not hardware" all green.

Step 4 - Adversarial self-audit.
  Grep the full diff for: TODO, FIXME, NotImplemented, mock, stub,
  placeholder, "for now", "simplified", empty except, unread config keys.
  Fix every hit or justify in writing. Then map every inventory item to
  file:line and to the test proving it. Missing either half means unfinished.

Step 5 - Completeness report.
  Inventory table with evidence links, commands run with outputs, explicit
  known limits, deferred items with my recorded sign-off.

WORK ORDERS, IN ORDER

WO-6  Agent framework: specialist loading by task class, delegation contract
      enforcement (blank-context prompt assembly, tool exclusivity hook,
      depth limit 2), critic agent with veto authority wired into task
      completion. Tests use fake subagents; no live model calls in CI.

WO-7  Specialist agents 1: perception-engineer, driver-engineer,
      pipeline-engineer. Each with task-class routing rules, required skill
      sets, and one golden exercising it end to end.

WO-8  Specialist agents 2: profiler, triage, safety-auditor, data-engineer,
      integrator. Same contract as WO-7.

WO-9  L1 corpus-first triage: deterministic corpus search path, ranked
      resolution rendering with provenance, corpus writeback on outcome,
      `deepgent triage` command with full flag surface.

WO-10 L9 scaffolding generators: driver skeleton + device tree fragment
      (RAG-grounded), ROS 2 package, DeepStream pipeline, TensorRT harness.
      Templates deterministic; model fills synthesis gaps only.

WO-11 L4 record/replay: on-target capture, content-addressed fixture store,
      deterministic replay, fixture-based perception regression goldens.

WO-12 L2 soak + L3 power: endurance orchestration with thermal profiles,
      anomaly snapshotting, degradation curves, energy-per-inference
      capture, power regression gates.

WO-13 L5 diff-run + L8 sweep: multi-board differential execution, lease-aware
      grid scheduling, early stopping, ranked provenance-linked results.

WO-14 L6 bisect + L7 upgrade-check: hardware bisection across commits and
      container digests; matrix-plus-golden upgrade impact reporting.

WO-15 L10 fleet watch: telemetry intake, incident auto-triage, farm
      reproduction, proposed fix with human approval gate.

WO-16 Skill infrastructure: frontmatter schema with applies_to and
      provenance, runtime fetch with auth and TTL cache, per-skill golden
      linkage, `deepgent skills` full command surface, and the CI gate that
      blocks any skill merge lacking a passing paired golden.

WO-17+ Skills, one session per skill, T0 first in catalog order. Each session
      delivers: the skill, its paired golden, and evidence that the golden
      fails or exceeds loop budget without it. No golden, no merge.

RULES THAT OVERRIDE ANYTHING ELSE
- Never author a skill without its paired golden in the same PR.
- Never write a version string outside versions.toml.
- Never bypass safety_gate, even in tests.
- Never include DeepMost-derived content.
- Never mark a work order complete without the Step 5 report.
- No em-dashes anywhere.

Begin with WO-6, Step 1 only.
```

---

# PART C: THE RULES THAT KEEP THIS HONEST

1. **The catalog is a map, not a queue.** 65 skills authored blind is 65
   liabilities: unreviewed domain claims that make the agent confidently wrong
   in exactly the areas where wrong is expensive. T0 is 11 skills. Everything
   else waits for a failing golden or corpus evidence to justify it.

2. **Agents are coordination cost.** Fourteen agents is a roster, not a
   runtime. Loading specialists by task class keeps per-task context lean; a
   task that loads more than three agents is a design smell worth investigating.

3. **Capability layers ship one at a time, fully.** Ten half-built layers is
   worse than three complete ones, because half-built features poison the
   telemetry that is supposed to tell you what to build next.

4. **Sequencing beats scope.** This document contains roughly a year of solo
   evenings. Its value is that you stop re-deciding what to build; its danger
   is treating it as a checklist to sprint through while your actual products
   wait. Build order comes from telemetry failure counts, not from this
   document's ordering.

5. **The kill criterion still stands.** If after WO-9 you are not reaching for
   deepgent on real work several times a week, stop expanding and reassess.
   The skills, goldens, and corpus remain valuable regardless of harness fate.

---

# RECONCILIATION WITH CURRENT STATE (2026-07-28)

This spec was written to be pasted "after Phase 0 is green". The repo is now
well past that: WO-1 through the mid-50s are merged. Much of Part A2 already
ships. Build order below follows Part C rule 4 (telemetry over document order),
not the spec's WO numbering. Spec WO labels are kept for traceability; repo
commits continue the sequential WO-NN numbering already in git history.

| Spec WO | Area | Repo status |
|---|---|---|
| WO-6 | Agent framework (specialists, delegation contract, critic) | NOT built. Only the 5 core agents exist; no task-class classifier, no tool-exclusivity hook, no critic. This is the real frontier. |
| WO-7 / WO-8 | The 9 specialist agents | NOT built. |
| WO-9 | L1 corpus-first triage (`deepgent triage`) | BUILT (knowledge/products.py triage, CLI command). Corpus writeback via telemetry_tap exists. |
| WO-10 | L9 scaffolding generators | BUILT (ros2-node, systemd, RAG-grounded driver scaffold). |
| WO-11 | L4 record/replay | BUILT (evals/replay.py, CLI `replay`). |
| WO-12 | L2 soak + L3 power | BUILT (evals/soak.py, thermal_envelope, power in tegrastats/generic metrics). |
| WO-13 | L5 diff-run + L8 sweep | BUILT (evals/differential.py, fleet, quant_sweep). |
| WO-14 | L6 bisect + L7 upgrade-check | BUILT (evals/bisect.py, knowledge/products.upgrade_check). |
| WO-15 | L10 fleet watch | PARTIAL. Telemetry store + incident tuples exist; the `deepgent watch` intake loop does not. |
| WO-16 | Skill infrastructure + golden-linkage CI gate | PARTIAL. Skill fetch/list/lifecycle/author exist; the paired-golden CI gate does not. |
| WO-17+ | The 65-skill catalog | PARTIAL. A handful of T0 skills exist; most do not, and none are golden-gated yet. |

Frontier, in build order: agent framework (spec WO-6) first, then specialists
(WO-7/8), then the skill-golden CI gate (WO-16) so every future skill is forced
to earn its context, then the T0 skills (WO-17+). The already-built capability
layers are audited against their spec inventory only when a golden or corpus
signal says they fall short, not pre-emptively.
