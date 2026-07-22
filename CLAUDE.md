    # CLAUDE.md

# deepgent

Domain-locked autonomous engineering agent for autonomous vehicles, computer vision,
and embedded systems. Takes a task from natural language to a verified artifact
running on target hardware at spec. Built on the Claude Agent SDK. Personal project
of Sherin Joseph Roy (github.com/Sherin-SEF-AI). Not a DeepMost AI product.

This file is the constitution for building deepgent. It is intentionally complete
for bootstrap. After Phase 0 scaffolding exists, migrate sections marked
[MIGRATE -> docs/...] into those files and slim this one to under 250 lines.
Anything that must be enforced (not just followed) is implemented as a hook or CI
gate, never left as prose here.

---

## 1. Prime directives

- Definition of done: it runs on target hardware and meets the stated metric
  (fps, p99 latency, mAP delta, memory, thermal). "Compiles and tests pass" is
  an intermediate state, never completion.
- Production-grade only. No placeholders, no mock data, no simulated results, no
  stub implementations, no "TODO: implement later" in delivered code. If something
  cannot be completed, say so explicitly and stop.
- Deterministic first. If a template, generator, compiler, linter, or script can do
  the step, it does. LLM calls are reserved for synthesis, design, and debugging.
- Never assert a hardware-specific fact (pin, register, voltage, timing, device
  tree binding, version compatibility) from model memory. Retrieve it from the
  knowledge layer with provenance, or verify it empirically on hardware, or state
  that it is unverified.
- Scope lock: AV, CV, embedded, robotics-adjacent edge AI only. Refuse everything
  else politely and immediately.
- Every task emits telemetry. Every verified fact feeds the compatibility matrix.
  Every resolved failure feeds the failure corpus. The data flywheel is not
  optional instrumentation; it is the product.
- IP hygiene (hard rule): deepgent is a personal project. Do not ingest, quote, or
  encode material derived from DeepMost AI repositories, sessions, incidents, or
  internal documents. Knowledge sources are public documentation, open source, and
  the owner's personal projects only.
- No em-dashes in any generated text, docs, comments, or commit messages.

## 2. What deepgent is

- A pip-installable CLI (`deepgent`, alias `dg`) plus an orchestrator built on the
  Claude Agent SDK, toolchain containers, MCP servers, and SSH-attached target
  boards.
- The client harness is open source. The knowledge layer (compatibility matrix,
  failure corpus, datasheet RAG) lives server-side behind an authenticated API and
  is queried at runtime, never shipped in the package. Skill packs are fetched at
  runtime with auth and cached with TTL. Air-gapped mode is a later enterprise
  concern, out of scope until Phase 5.
- PyPI name `deepgent` is verified free as of 2026-07-22. Reserve it with a 0.0.1
  placeholder release immediately in Phase 0.

## 3. Architecture

Five layers. Do not add a sixth without updating this file first.

1. Agent core: Claude Agent SDK orchestration, subagents, sessions, routing.
2. Knowledge: skill packs (client-cached), datasheet RAG, compatibility matrix,
   failure corpus (all server-side APIs).
3. Execution: version-pinned toolchain containers, deterministic generators.
4. Verification: static analysis, tests, on-target runs, metric capture.
5. Interface: CLI, and later HTTP API / CI mode on the same internal API.

### Task lifecycle (every task, no exceptions)

1. Intake: deterministic classifier assigns task class, risk tier, skills,
   container set. LLM classification only when deterministic rules are ambiguous.
2. Context assembly: load `.deepgent/project.md`, resolve skills, prefetch RAG
   for named hardware.
3. Plan: architect subagent produces a typed plan artifact for non-trivial tasks
   (risk tier >= 2 or multi-component). Trivial tasks skip to execution.
4. Execute: generators first, then implementer subagent for synthesis.
5. Verify: build in the pinned container, static analysis, unit tests. Failures
   loop back with structured error context, never raw logs.
6. Hardware validate: deploy to the leased board, run, capture metrics. Gated
   operations require approval.
7. Report: metrics, diff summary, artifacts under `.deepgent/runs/<id>/`.
   Update project state. Emit telemetry, matrix claims, corpus tuples.

## 4. Repository layout

```
deepgent/
  CLAUDE.md                  # this file
  pyproject.toml             # uv-managed, package name deepgent
  versions.toml              # single source of truth for external versions
  src/deepgent/
    cli/                     # typer-based CLI entry points
    core/                    # orchestrator, session, routing, budgets
    agents/                  # subagent definitions (AgentDefinition builders)
    hooks/                   # hook callbacks (safety, lint, budget, scope)
    generators/              # deterministic template generators
    containers/              # container manifests + build logic
    boards/                  # board farm client, SSH runner, metrics capture
    knowledge/               # clients for RAG, matrix, corpus, skills fetch
    evals/                   # golden task runner, scoring, regression gate
    telemetry/               # sqlite store, schemas, exporters
    config/                  # settings models (pydantic), loaders
  skills/                    # local dev copies of skill packs (SKILL.md dirs)
  golden/                    # golden task YAMLs + fixtures
  server/                    # knowledge API (FastAPI), separate deploy, private
  docs/                      # architecture.md, schemas.md, runbooks/
  tests/                     # pytest; markers: unit, integration, hardware
  .github/workflows/         # ci.yml, hardware.yml (self-hosted runner)
  .claude/                   # settings.json, agents/, hooks config for dev
```

## 5. Environment and tooling

- Python 3.12. `uv` for everything: `uv sync`, `uv run`, `uv build`. Never pip
  directly, never poetry.
- Lint/format: `ruff check --fix` and `ruff format`. Types: `mypy --strict` on
  `src/`. Both are CI gates.
- Tests: `pytest -m "not hardware"` locally and in CI;
  `pytest -m hardware` only via the board runner workflow.
- Containers: Docker with buildx. aarch64 cross builds use qemu binfmt. Jetson
  containers base on `nvcr.io/nvidia/l4t-*` images matching `versions.toml`.
- Commit style: conventional commits (`feat:`, `fix:`, `chore:`, `eval:`,
  `skill:`). One logical change per commit. Never commit secrets, board IPs, or
  `.deepgent/` run artifacts.
- Before reporting any coding task complete: `uv run ruff check`,
  `uv run mypy src/`, `uv run pytest -m "not hardware"` all green.

## 6. Coding standards

- Every module: typed signatures, docstrings on public APIs, `structlog` logging,
  explicit exception types. No bare `except`, no `print` outside the CLI layer.
- Config via pydantic-settings; no magic constants; everything overridable by env
  var with the `DEEPGENT_` prefix.
- Errors that reach the user are actionable: what failed, on which layer, next
  step. Raw tracebacks only at `--debug`.
- Async where I/O bound (SSH, HTTP, SDK streaming); no threads unless justified
  in a comment.
- Comments explain non-obvious decisions only, never narrate the code.

## 7. Claude Agent SDK usage (verified against docs, 2026-07)

- Package: `claude-agent-sdk` (bundles the Claude Code CLI since v0.1.8).
  Import surface used: `query`, `ClaudeSDKClient`, `ClaudeAgentOptions`,
  `AgentDefinition`, `HookMatcher`, `create_sdk_mcp_server`, `tool`.
- One-shot tasks use `query()`; interactive mode uses `ClaudeSDKClient`.
- Always set explicitly (never rely on ambient defaults):
  `allowed_tools`, `permission_mode`, `mcp_servers`, `agents`, `hooks`,
  `setting_sources=["project"]` (loads repo CLAUDE.md into worker context),
  `cwd`, `max_turns`, `model`.
- Subagent contexts are blank: pass all needed state (plan, file paths, metrics
  targets, prior errors) in the delegation prompt. Nothing is implicitly shared.
- In-process tools use `@tool` + `create_sdk_mcp_server`; external MCP servers
  (board-farm, datasheet-rag) attach as stdio/http entries in `mcp_servers`.
- Python hook events available: PreToolUse, PostToolUse, PostToolUseFailure,
  UserPromptSubmit, Stop, SubagentStop, SubagentStart, PreCompact, Notification,
  PermissionRequest. Blocking decisions are returned from PreToolUse /
  PermissionRequest callbacks. Confirm exact return schema against the current
  SDK reference at implementation time; do not code it from memory.
- Pin the SDK version in pyproject; review its changelog before every bump.

## 8. Subagents

Defined programmatically in `src/deepgent/agents/`. All five exist from Phase 0
even if thin.

| Agent | Role | Tools | Model default |
|---|---|---|---|
| architect | plans, interfaces, acceptance criteria | Read, Glob, Grep, knowledge MCPs | opus-class |
| implementer | writes code, runs generators | Read, Write, Edit, Bash, generators MCP | sonnet-class |
| verifier | builds, static analysis, tests | Bash (containerized), Read | sonnet-class |
| hardware-runner | deploy, execute, measure on boards | board-farm MCP only | sonnet-class |
| researcher | all RAG/matrix/corpus queries | knowledge MCPs, WebSearch | haiku/sonnet |

- Only researcher may call knowledge APIs; keeps retrieval auditable.
- Only hardware-runner may touch boards; keeps safety gates in one path.
- Model IDs live in `versions.toml` under `[models]`, not in code.

## 9. Model routing and budgets

- Route by task class: classification/mechanical edits -> haiku tier; standard
  implementation/verification -> sonnet tier; architecture, cross-component
  debugging, plan review -> opus tier.
- Per-task budget cap (default USD 2.00, config `budget.per_task_usd`) enforced
  by a Stop/PostToolUse hook that halts and reports at 90%.
- Prompt caching: skills and system context are cache-stable; never interpolate
  volatile values (timestamps, run ids) into cached blocks.
- Log tokens and cost per task into telemetry; `deepgent report` surfaces them.

## 10. Hooks (enforcement layer)

Implemented in `src/deepgent/hooks/`, registered on every session. These are the
law; prose elsewhere is guidance.

- scope_lock (UserPromptSubmit): out-of-domain request -> refuse with one line.
- safety_gate (PreToolUse on board-farm tools): operations tagged flash, gpio,
  power, daemon-restart, fs-destructive require interactive approval unless
  whitelisted in `.deepgent/gates.toml`. CI mode auto-denies non-whitelisted.
- misra_gate (PostToolUse on Write/Edit of `*.c/*.cc/*.cpp/*.h/*.hpp`): run
  clang-tidy profile + cppcheck MISRA addon inside the toolchain container;
  block completion on new violations; report as structured findings.
- budget_guard (PostToolUse): enforce section 9 caps.
- fact_guard (PostToolUse on researcher): every matrix/RAG answer must carry
  provenance fields; strip and flag any that do not.
- telemetry_tap (Stop, SubagentStop, PostToolUseFailure): persist task record,
  corpus tuple candidates, matrix claim candidates.

## 11. Skill packs

[MIGRATE -> docs/skills.md after Phase 0]

- Format: Agent Skills convention. Directory per skill with `SKILL.md`
  (frontmatter: name, description; body: instructions), optional `references/`,
  `scripts/`. Keep SKILL.md under ~150 lines; deep detail goes in references
  loaded on demand.
- Launch set (Phase 1 builds first three):
  jetson-bringup, tensorrt-quantization, ros2-systems,
  deepstream-pipelines, camera-bringup-gmsl2, can-bus, sensor-fusion,
  training-pipelines, embedded-c-safety, hailo-toolchain.
- Content rules: only non-obvious, durable, version-tagged knowledge. Nothing
  the base model already knows (test by running goldens with the skill absent).
  Every claim carries source + version applicability. No licensed standards text
  (MISRA/ISO rules are enforced by tooling, described only in own words).
- Merge gate: a skill change merges only if the golden suite improves or holds
  with equal-or-lower loop count. `deepgent evals run --diff` produces the
  evidence. Skills are code; they go through PRs and CI.

## 12. MCP servers

[MIGRATE -> docs/mcp.md after Phase 0]

- board-farm (local, Phase 2): tools `list_boards`, `lease`, `release`,
  `deploy`, `exec`, `capture_metrics`, `power`. Board registry in
  `~/.deepgent/boards.toml`. All destructive tools tagged for safety_gate.
- datasheet-rag (server, Phase 3): tools `search(query, chip?, l4t?)`,
  `get_chunk(id)`. Returns chunks with {doc, section, version, chip, hash}.
  Ingestion pipeline (server side): table-aware PDF extraction, chunk by
  section/register block, metadata: chip, silicon rev, doc version, applicable
  L4T/JetPack range. Errata ingested separately with elevated retrieval weight.
- knowledge-matrix (server, Phase 4): `query_claim(stack...)` ->
  {status: verified_pass|verified_fail|unknown, evidence_run_id, verified_at,
  versions}. Claims are only written by the eval/verification pipeline, never by
  the model directly.
- failure-corpus (server, Phase 4): `search_symptom(text, hw, versions)` ->
  ranked tuples {symptom, hw_config, version_matrix, root_cause, fix,
  verification_run_id}.
- artifact-store (local first): content-addressed storage of engines, wheels,
  images, reports under `.deepgent/runs/`.
- carla-sim (Phase 5): scenario run + metrics for AV behavior tasks.

## 13. Versions manifest

`versions.toml` is the only place external versions appear. Code and docs read
from it; nothing hardcodes a version string. Seeded 2026-07-22 (verified):

```toml
[jetson.jp6]           # production line for AGX Orin targets
jetpack = "6.2"
l4t = "36.4.3"
cuda = "12.6"
tensorrt = "10.3"
cudnn = "9.3"

[jetson.jp7]           # newer line; not used until a target requires it
jetpack = "7.2"
l4t = "39.2"
cuda = "13.2.1"
tensorrt = "10.16.2"

[ros2]
default = "jazzy"      # containerized; mature ecosystem on Ubuntu 24.04
lts_latest = "lyrical" # released 2026-05, Ubuntu 26.04; adopt via containers
                       # only after goldens pass on it
jp6_native = "humble"  # L4T r36 rootfs is Ubuntu 22.04

[deepstream]
version = "pinned-per-container"  # resolve against JetPack at container build,
                                  # verify with a smoke golden, record actual
```

- Rule: on any `versions.toml` change, rebuild containers and run the full
  golden suite before merge. The diff report is the upgrade changelog.
- A scheduled job (Phase 4) watches NVIDIA/ROS release feeds and opens a PR
  bumping this file.

## 14. Board farm

- Registry `~/.deepgent/boards.toml`: id, host, ssh_user, key_path, type,
  l4t/os, capabilities (csi, can, gpio, hailo), power_ctl (none|smartplug|pdu).
- Initial boards: one AGX Orin 64GB dev kit (agx-orin, r36.4.x) and one
  Pi 5 + Hailo accelerator node. Add via `deepgent boards add`; never hardcode.
- Lease model: one task per board; queued otherwise. Leases auto-expire.
- Metrics capture on Jetson: tegrastats parser + `trtexec` timing + pipeline
  fps probes; store raw + parsed in the run directory.
- Safety: watchdog on every remote exec (timeout, cleanup); never leave a board
  in a modified daemon state after a failed run; restore on lease release.

## 15. CLI surface (contract; keep stable)

```
deepgent "<task>" [--board ID] [--dry-run] [--budget USD] [--attach PATH]
deepgent                      # interactive session
deepgent plan "<task>"        # write plan artifact only
deepgent run --plan FILE
deepgent resume
deepgent init | setup | doctor
deepgent boards add|list|test|remove
deepgent evals run [--diff] [--task ID]
deepgent skills list|add|update [--test]
deepgent rag ingest FILE --chip X [--l4t RANGE]     # owner/server mode
deepgent report [RUN_ID]
deepgent ci --task "<task>" --budget USD            # non-interactive, JSON out
deepgent sweep --grid FILE                          # Phase 5
```

- `--dry-run` stops after verification, never touches hardware.
- CI mode: machine-readable JSON to stdout, exit code = pass/fail, gates
  auto-deny unless whitelisted in policy.

## 16. Config files

- `~/.deepgent/config.toml`: API keys ref (env or keyring, never plaintext),
  model tiers, default budgets, telemetry opt-in.
- `.deepgent/project.md`: agent-maintained project state; updated every task;
  human-readable; committed only if the repo owner opts in.
- `.deepgent/config.toml`: default board, budget overrides, gate policy path.
- `.deepgent/gates.toml`: whitelisted gated operations, per board, per op type.

## 17. Golden tasks and evals

[MIGRATE -> docs/evals.md after Phase 0]

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

## 18. Telemetry, matrix, corpus schemas

[MIGRATE -> docs/schemas.md after Phase 0]

- task_record: id, ts, class, board, model_mix, tokens, usd, wall_s, loops,
  outcome, failure_tag (taxonomy below), artifacts_path.
- failure taxonomy v0: build_toolchain, build_deps, static_analysis, unit_test,
  deploy_ssh, runtime_crash, perf_miss, accuracy_miss, thermal, flaky_hw,
  knowledge_gap, harness_bug.
- matrix_claim: {stack: {l4t, cuda, trt, ds, ros, sensor, serdes}, claim,
  status, evidence_run_id, verified_at}. Written only by verified runs.
- corpus_tuple: {symptom, hw_config, versions, root_cause, fix_diff_ref,
  verification_run_id, ts}. Candidate tuples auto-drafted by telemetry_tap on
  any failed->passed transition; owner approves before server upload.

## 19. Knowledge layer split (do not violate)

- Ships in package: harness code, generators, container manifests, CLI.
- Server-side only: RAG corpus + index, compatibility matrix, failure corpus.
  Clients get query APIs, metered, rate-limited; never bulk export endpoints.
- Skill packs: fetched with auth, cached with TTL, licensed no-redistribution.
- Telemetry upload is opt-in for external users, on by default for the owner.

## 20. Security

- Secrets only via env or OS keyring; `deepgent doctor` audits for leaks.
- SSH: key auth only, per-board keys, no agent forwarding to boards.
- Never store credentials, board IPs, or personal paths in the repo, skills,
  telemetry uploads, or corpus tuples (sanitizer in telemetry_tap).
- The server component validates auth on every request; no anonymous reads.

## 21. Licensing and distribution

- Client/harness: Apache-2.0. `server/` and skill content: proprietary, all
  rights reserved (separate private repo before first external user).
- Release: `uv build` + trusted publishing to PyPI from CI on tag. Semver;
  0.x until Phase 4 exit.

## 22. Phase plan and exit criteria

- Phase 0 (bootstrap): repo scaffold per section 4; SDK skeleton with all five
  subagents; jp6 cross-compile container; hooks scope_lock + safety_gate +
  budget_guard live; golden gt-0001 (build + deploy + run a trivial CUDA
  kernel on agx-orin, capture tegrastats) passing end to end; PyPI 0.0.1
  placeholder published. Exit: `deepgent "gt-0001 task"` green from a clean
  clone on a second machine.
- Phase 1 (knowledge v0): skills jetson-bringup, tensorrt-quantization,
  ros2-systems; misra_gate live; 10 goldens. Exit: goldens pass with skills,
  and >=3 of them fail or exceed loop budget without skills (proves value).
- Phase 2 (hardware): board-farm MCP, lease model, metrics capture, gates.toml.
  Exit: two boards, concurrent tasks queued safely, zero unsafe ops in log.
- Phase 3 (RAG): server skeleton + datasheet-rag; ingest owner BOM datasheets
  (public docs only); fact_guard live. Exit: pin/binding questions answered
  with provenance; hallucinated-fact goldens pass.
- Phase 4 (flywheel): telemetry complete, matrix + corpus services, regression
  gates in CI, release-watch job. Exit: 25 goldens, first 50 corpus tuples,
  first 200 verified matrix claims, upgrade report generated for a real
  JetPack bump.
- Phase 5 (surfaces): ci mode hardening, sweep, HTTP API, carla-sim,
  BringupBench public subset. Data-driven fine-tune decision only now.

## 23. Never do

- Never mark a task complete without on-target metrics when the task specifies
  hardware behavior.
- Never bypass safety_gate, even in tests (use the fake board fixture).
- Never write version strings outside `versions.toml`.
- Never put DeepMost-derived content anywhere in this project.
- Never invent datasheet facts; unknown is an acceptable answer, fabrication
  is not.
- Never ship knowledge content inside the client package.
- Never use em-dashes.


## 24. Github URL
https://github.com/Sherin-SEF-AI/deepgent.git