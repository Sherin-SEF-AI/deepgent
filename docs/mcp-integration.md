# Integrating deepgent with Claude (MCP)

deepgent can run as an MCP server so an external Claude client (Claude Code,
Claude Desktop, or a claude.ai connector) can call its tools directly.

## Install deepgent on your PATH (one command)

```
./install.sh
```

This runs `uv tool install --editable ".[gui]"`, putting `deepgent`, `dg`, and
`deepgent-gui` on your PATH. If the shell can't find them afterward, run
`uv tool update-shell` and restart the shell.

## Run the server

```
deepgent mcp                 # stdio server, full tool surface (no run_task)
deepgent mcp --allow-task    # also expose run_task (costs API, edits files)
```

## Tools exposed

`deepgent mcp` exposes deepgent's full tool surface. String arguments accept
either inline JSON or a path to a file with that JSON; comma lists are plain
`a,b,c`; stacks are `key=value,key=value`.

### Deterministic (no hardware, no API cost)

- `hw_check(config)` - pin / I2C / power conflict detection for a carrier board
- `boards_catalog(family?)` - the supported board-type catalog
- `matrix_query(claims, stack, component, rules?)` - compatibility with inference
- `matrix_analyze(claims, component, universe?, rules?)` - contradictions + next cell
- `accuracy_score(predictions, truth, kind, iou)` - VOC mAP / top-1
- `skills_eval(ablation)` - skill-lift promote/keep/retire
- `facts(assertions)` - confidence-calibrated fact arbitration
- `reflect(tool, error)` - taxonomy-classified root-cause replan
- `generate_ros2_node(package, node, sub_topic?, pub_topic?)` - scaffold an
  ament_python ROS 2 node package
- `generate_systemd(name, exec_start, description?, user?, watchdog?)` - scaffold
  a hardened systemd unit
- `host_doctor()` - environment diagnostics (uv, docker, qemu, SDK, key)
- `host_profile()` - detected device class, arch, accelerator, cpu, ram
- `telemetry_summary()` - task counts, success rate, spend, learned calibrations
- `boards_list()` - the registered target boards
- `errata_scan(chips, errata)` - scan the tree for chip-errata code patterns
- `bom_advise(candidates, constraints?)` - filter verified stacks to a fps/power/cost budget
- `skills_author(tuples?, min_cluster?)` - draft SKILL.md candidates from clustered corpus tuples

### Knowledge layer (returns a note if the knowledge server is not configured)

- `premortem(symptom, hw?, stack?)` - corpus + matrix failure-mode pre-mortem
- `triage(symptom, hw?)` - corpus-first debugging before any LLM reasoning
- `upgrade_check(current_stack, proposed)` - matrix impact report for a version move
- `scaffold_driver(device, compatible, chip, kind?)` - RAG-grounded driver + DT fragment

### On-target runners (need a registered board; return an error if none is reachable)

Register a board first with `deepgent boards add`. Each runs over SSH and
captures metrics under `.deepgent/runs/`.

- `profile_thermal(board, workload, hold?, modes?, tj_max?)` - thermal/DVFS envelope
- `profile_latency(board, command, budget_ms?, capture?)` - per-stage p99 latency
- `profile_nsight(board, command, capture?)` - bottleneck classification
- `cuda_check(board, run, build?, tools?)` - compute-sanitizer gate
- `fleet(command, boards)` - benchmark across a fleet, compat+perf matrix
- `soak(board, hours, workload?, tj_max?)` - endurance run with anomaly snapshots
- `differential(artifact, boards, command)` - one artifact across boards, compared
- `accuracy_gate(board, command, metric, baseline?, tolerance?, capture?)` - on-device eval gate
- `quant_sweep(board, command, precisions?, batches?, devices?, accuracy_metric?, capture?)` - precision Pareto sweep
- `select_model(board, manifest, ...)` - pick candidates meeting a deploy budget
- `shadow(board, fixture, incumbent, candidate, remote_path?, kind?, iou?)` - diff two models on a replayed fixture
- `replay(action, name?, board?, command?, remote_path?)` - record/replay/list sensor-stream fixtures
- `bisect(task, good, bad)` - auto-bisect a regressed golden to the breaking commit

### Gated (only with `--allow-task`, because it costs API and edits files)

- `run_task(task, budget)` - the full agent loop (writes code, reviews, tests)

## Register with Claude Code

```
claude mcp add deepgent -- deepgent mcp
# or, to allow the agent to run tasks:
claude mcp add deepgent -- deepgent mcp --allow-task
```

## Register with Claude Desktop

Add to `claude_desktop_config.json` (Settings > Developer > Edit Config):

```json
{
  "mcpServers": {
    "deepgent": {
      "command": "deepgent",
      "args": ["mcp"]
    }
  }
}
```

Use `"args": ["mcp", "--allow-task"]` to expose the task runner. The
`ANTHROPIC_API_KEY` in deepgent's environment is only needed for `run_task`;
the deterministic tools need no key.

## claude.ai web connector (HTTP + auth)

claude.ai reaches a remote MCP server over HTTP, so run the streamable-http
transport with a bearer token and expose it at a URL claude.ai can reach.

```
export DEEPGENT_MCP_TOKEN="$(openssl rand -hex 24)"    # shared secret
deepgent mcp --transport streamable-http --host 0.0.0.0 --port 8000
```

- When `DEEPGENT_MCP_TOKEN` is set, every HTTP request must send
  `Authorization: Bearer <token>`; without it the server warns that the
  endpoint is unauthenticated.
- Expose it publicly with a tunnel or reverse proxy (for example
  `cloudflared tunnel --url http://localhost:8000`) and use the resulting
  https URL when adding the custom connector in claude.ai, with the same bearer
  token as the auth header.
- Prefer TLS in front of the server (the tunnel/proxy provides it); the bearer
  token is the access control, the proxy is the transport security.

## Notes

- The stdio transport owns stdout for the MCP JSON-RPC channel; deepgent's logs
  go to stderr, so never mix other output onto stdout when running as a server.
- The deterministic tools preserve deepgent's guarantees: no hardware fact is
  fabricated, and every conflict/claim/score is computed from the input.
