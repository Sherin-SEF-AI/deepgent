"""deepgent as an MCP server, so an external Claude client (Claude Code,
Claude Desktop, or a claude.ai connector) can call deepgent's tools.

Exposes the deterministic, no-hardware, no-API tools directly, plus an
optional run_task tool (gated by allow_task) that runs the full agent loop and
therefore costs API and edits files. String arguments accept either inline
content or a path to a file with that content.
"""

import json
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from deepgent.errors import DeepgentError as _DeepgentError

_ASGIApp = Callable[[Any, Any, Any], Awaitable[None]]


def _settings() -> Any:
    from deepgent.config import load_settings

    return load_settings()


def _read(arg: str) -> str:
    """Inline content, or the contents of a file if arg is an existing path."""
    if len(arg) < 4096 and "\n" not in arg:
        try:
            candidate = Path(arg)
            if candidate.is_file():
                return candidate.read_text()
        except OSError:
            pass  # not a usable path (too long, invalid char): treat as inline
    return arg


def hw_check(config: str) -> str:
    """Detect pin/mux, I2C address, and power-rail conflicts in a carrier-board
    design. config is the hardware-config JSON (peripherals + rails), inline or
    a file path. Peripherals lacking datasheet provenance are flagged."""
    from deepgent.knowledge.hardware_check import check_conflicts, load_config

    return check_conflicts(load_config(_read(config))).render()


def boards_catalog(family: str = "") -> str:
    """List the board types deepgent targets (Jetson series, Raspberry Pi
    models, Hailo/Coral AI accelerators, hosts). Optionally filter by family:
    jetson, raspberry-pi, accelerator, host. Categorical only; verify specs."""
    from deepgent.boards import list_catalog, render_catalog

    return render_catalog(list_catalog(family or None))


def matrix_query(claims: str, stack: str, component: str, rules: str = "") -> str:
    """Query the compatibility matrix for a component on a stack, with
    transitive inference. claims is the claims JSON; stack is 'key=value,...';
    rules is optional version-equivalence JSON. Returns works/fails/unknown
    with a confidence and the basis."""
    from deepgent.knowledge.matrix import load_claims, load_rules, query

    claim_list = load_claims(_read(claims))
    rule_set = load_rules(_read(rules)) if rules else {}
    stack_dict = dict(kv.split("=", 1) for kv in stack.split(",") if "=" in kv)
    verdict = query(claim_list, stack_dict, component, rule_set)
    works = "unknown" if verdict.works is None else ("works" if verdict.works else "fails")
    return f"{component}: {works} (confidence {verdict.confidence:.2f}, {verdict.basis})"


def matrix_analyze(claims: str, component: str, universe: str = "", rules: str = "") -> str:
    """Find contradictions in the compatibility matrix and the next unverified
    cell worth testing (active learning). claims/universe/rules are JSON,
    inline or paths."""
    from deepgent.knowledge.matrix import analyze, load_claims, load_rules

    claim_list = load_claims(_read(claims))
    rule_set = load_rules(_read(rules)) if rules else {}
    cells = json.loads(_read(universe)) if universe else None
    return analyze(claim_list, component, cells, rule_set).render()


def accuracy_score(predictions: str, truth: str, kind: str = "detection", iou: float = 0.5) -> str:
    """Score predictions against ground truth. kind='detection' computes VOC
    mAP@iou from prediction/GT boxes; kind='classification' computes top-1 from
    predicted/true labels. Arguments are JSON, inline or paths."""
    from deepgent.evals.accuracy import load_detections, load_ground_truths
    from deepgent.evals.metrics import classification_accuracy, mean_average_precision

    if kind == "detection":
        value = mean_average_precision(
            load_detections(_read(predictions)), load_ground_truths(_read(truth)), iou
        )
        return f"mAP@{iou:g}: {value:.4f}"
    predicted = [str(x) for x in json.loads(_read(predictions))]
    labels = [str(x) for x in json.loads(_read(truth))]
    return f"top-1: {classification_accuracy(predicted, labels):.4f}"


def skills_eval(ablation: str) -> str:
    """Measure each skill's causal lift from ablation data and recommend
    promote/keep/retire. ablation is a JSON array of {skill, present, passed,
    loops}, inline or a path."""
    from deepgent.knowledge.skill_lifecycle import analyze_lifecycle, load_ablation

    return analyze_lifecycle(load_ablation(_read(ablation))).render()


def facts(assertions: str) -> str:
    """Arbitrate conflicting facts by calibrated provenance confidence.
    assertions is a JSON object keyed by subject, each a list of
    {value, source[, base_override]}; model-memory sources are refused."""
    from deepgent.knowledge.fact_confidence import FactAssertion, arbitrate_all
    from deepgent.telemetry import TelemetryStore

    raw = json.loads(_read(assertions))
    grouped = {
        subject: [
            FactAssertion(
                subject=subject,
                value=str(item["value"]),
                source=str(item["source"]),
                base_override=item.get("base_override"),
            )
            for item in items
        ]
        for subject, items in raw.items()
    }
    calibration = TelemetryStore().fact_reliability()
    return arbitrate_all(grouped, calibration).render()


def reflect(tool: str, error: str) -> str:
    """Classify a tool failure against the taxonomy and produce a targeted,
    root-cause replan (with severity) instead of a blind retry."""
    from deepgent.core.reflexion import reflect as _reflect

    return _reflect(tool, error).render()


def _csv(value: str) -> list[str]:
    return [v.strip() for v in value.split(",") if v.strip()]


def _stack(value: str) -> dict[str, str]:
    return dict(kv.split("=", 1) for kv in value.split(",") if "=" in kv)


# --- generators (deterministic) --------------------------------------------


def generate_ros2_node(
    package: str, node: str, sub_topic: str = "input", pub_topic: str = "output"
) -> str:
    """Scaffold a buildable ament_python ROS 2 node package. Returns each
    generated file's path and contents."""
    from deepgent.generators import Ros2NodeSpec, scaffold_ros2_node

    out = scaffold_ros2_node(Ros2NodeSpec(package, node, sub_topic, pub_topic))
    blocks = [f"=== {rel} ===\n{content}" for rel, content in out.files.items()]
    return "\n\n".join(blocks) + "\n\nnext:\n" + "\n".join(f"- {t}" for t in out.todos)


def generate_systemd(
    name: str, exec_start: str, description: str = "", user: str = "", watchdog: int = 0
) -> str:
    """Scaffold a hardened systemd .service unit (restart, clean stop, optional
    watchdog)."""
    from deepgent.generators import SystemdUnitSpec, scaffold_systemd_unit

    out = scaffold_systemd_unit(
        SystemdUnitSpec(
            name=name,
            exec_start=exec_start,
            description=description,
            user=user or None,
            watchdog_sec=watchdog or None,
        )
    )
    return "\n\n".join(f"=== {rel} ===\n{c}" for rel, c in out.files.items())


# --- host / telemetry / boards ---------------------------------------------


def host_doctor() -> str:
    """Run deepgent's environment diagnostics (host, python, uv, docker, qemu,
    versions, SDK, API key)."""
    from deepgent.host.diagnostics import run_checks

    return "\n".join(f"[{'OK' if c.ok else 'FAIL'}] {c.name}: {c.detail}" for c in run_checks())


def host_profile() -> str:
    """Show the detected host profile (device class, arch, accelerator, cpu, ram)."""
    from deepgent.host import detect_host

    p = detect_host()
    return (
        f"device_class={p.device_class} arch={p.arch} accelerator={p.accelerator} "
        f"cpu={p.cpu_count} ram_mb={p.ram_mb} os={p.os}"
    )


def telemetry_summary() -> str:
    """Aggregate telemetry: task count, success rate, spend, and learned
    budget/fact calibrations."""
    from deepgent.telemetry import TelemetryStore

    return TelemetryStore().summary().render()


def boards_list() -> str:
    """List the registered target boards."""
    from deepgent.boards import load_registry

    boards = load_registry()
    if not boards:
        return "no boards registered (deepgent boards add ...)"
    lines = []
    for b in boards.values():
        where = "this machine" if b.transport == "local" else f"{b.ssh_user}@{b.host}"
        lines.append(f"{b.id} [{b.transport}] {where} type={b.type} l4t={b.l4t or '-'}")
    return "\n".join(lines)


# --- knowledge / RAG products (degrade gracefully) -------------------------


async def premortem(symptom: str, hw: str = "", stack: str = "") -> str:
    """Predict failure modes for a task from the corpus and matrix. Needs the
    knowledge layer; returns a note if it is not configured."""
    from deepgent.knowledge import build_rag_client
    from deepgent.knowledge.premortem import premortem as _premortem

    client = build_rag_client(_settings())
    try:
        report = await _premortem(client, symptom, hw=hw or None, stack=_stack(stack) or None)
        return report.render()
    except Exception as exc:  # knowledge server absent / unreachable
        return f"knowledge layer unavailable: {exc}"
    finally:
        await client.aclose()


async def triage(symptom: str, hw: str = "") -> str:
    """Corpus-first debugging: consult the failure corpus before any LLM
    reasoning. Needs the knowledge layer."""
    from deepgent.knowledge import build_rag_client
    from deepgent.knowledge import triage as _triage

    client = build_rag_client(_settings())
    try:
        return (await _triage(client, symptom, hw=hw or None)).render()
    except Exception as exc:
        return f"knowledge layer unavailable: {exc}"
    finally:
        await client.aclose()


async def upgrade_check(current_stack: str, proposed: str) -> str:
    """Impact report for a version move: query the matrix for every component
    that changes between current and proposed. Stacks are 'key=value,...'.
    Needs the knowledge layer."""
    from deepgent.knowledge import build_rag_client
    from deepgent.knowledge import upgrade_check as _upgrade_check

    client = build_rag_client(_settings())
    try:
        report = await _upgrade_check(client, _stack(current_stack), _stack(proposed))
        return report.render()
    except Exception as exc:
        return f"knowledge layer unavailable: {exc}"
    finally:
        await client.aclose()


def bom_advise(candidates: str, constraints: str = "") -> str:
    """Filter verified stack options to those meeting fps/power/cost limits,
    cheapest first. candidates is a JSON array of {board, stack, fps, power_w,
    cost_usd, evidence_run_id}; constraints is 'min_fps=..,max_power_w=..,
    max_cost_usd=..'. Never invents a stack, only filters measured ones."""
    from deepgent.knowledge import BomCandidate, BomConstraints
    from deepgent.knowledge import bom_advise as _bom_advise

    def _num(mapping: dict[str, str], key: str) -> float | None:
        return float(mapping[key]) if key in mapping else None

    limits = _stack(constraints)
    constraint = BomConstraints(
        min_fps=_num(limits, "min_fps"),
        max_power_w=_num(limits, "max_power_w"),
        max_cost_usd=_num(limits, "max_cost_usd"),
    )
    parsed = [
        BomCandidate(
            board=c["board"],
            stack=c.get("stack", {}),
            fps=c.get("fps"),
            power_w=c.get("power_w"),
            cost_usd=c.get("cost_usd"),
            evidence_run_id=c["evidence_run_id"],
        )
        for c in json.loads(_read(candidates))
    ]
    passing = _bom_advise(parsed, constraint)
    if not passing:
        return "no candidate stack satisfies the constraints"
    lines = [
        f"{c.board}: {c.stack} fps={c.fps} power_w={c.power_w} "
        f"cost=${c.cost_usd} (evidence {c.evidence_run_id})"
        for c in passing
    ]
    return "\n".join(lines)


def errata_scan(chips: str, errata: str) -> str:
    """Scan the working tree for code patterns from chip errata affecting a BOM.
    chips is a comma list of chip ids; errata is a JSON array of
    {id, chip, title, patterns[], advisory}, inline or a file path."""
    from deepgent.knowledge import Erratum, scan_errata

    entries = json.loads(_read(errata))
    defs = [
        Erratum(
            id=e["id"],
            chip=e["chip"],
            title=e.get("title", ""),
            patterns=tuple(e["patterns"]),
            advisory=e.get("advisory", ""),
        )
        for e in entries
    ]
    result = scan_errata(Path.cwd(), defs, {c for c in _csv(chips)})
    return result.render_advisory()


async def scaffold_driver(device: str, compatible: str, chip: str, kind: str = "i2c") -> str:
    """Scaffold a RAG-grounded driver skeleton (i2c or v4l2) plus a device-tree
    fragment for a peripheral. Grounds register facts in the datasheet RAG, so
    it needs the knowledge layer."""
    from deepgent.generators import scaffold_driver as _scaffold_driver
    from deepgent.generators import spec_from_chunks
    from deepgent.knowledge import build_rag_client

    client = build_rag_client(_settings())
    try:
        chunks = await client.search(f"{device} registers i2c address", chip=chip)
    except Exception as exc:
        return f"knowledge layer unavailable: {exc}"
    finally:
        await client.aclose()
    out = _scaffold_driver(spec_from_chunks(device, compatible, kind, chunks))
    blocks = [f"=== {rel} ===\n{content}" for rel, content in out.files.items()]
    return "\n\n".join(blocks) + "\n\nnext:\n" + "\n".join(f"- {t}" for t in out.todos)


# --- on-target runners (continued) -----------------------------------------


async def shadow(
    board: str,
    fixture: str,
    incumbent: str,
    candidate: str,
    remote_path: str = "/tmp/deepgent-shadow/stream.bin",
    kind: str = "detection",
    iou: float = 0.5,
) -> str:
    """Replay a recorded fixture through an incumbent and a candidate model on a
    board and diff their behavior. Requires a registered board and a fixture
    recorded with the replay tool."""
    from deepgent.evals.shadow import ShadowRunner

    try:
        run_dir = _run_dir(f"shadow-{board}")
        diff = await ShadowRunner(board, Path.cwd()).run(
            fixture, incumbent, candidate, remote_path, run_dir, kind, iou
        )
        return diff.render()
    except _DeepgentError as exc:
        return f"error: {exc}"


async def replay(
    action: str,
    name: str = "",
    board: str = "",
    command: str = "",
    remote_path: str = "",
) -> str:
    """Record real sensor streams as deterministic fixtures, replay them, or
    list them. action is record|replay|list. record/replay need name, board,
    command, and remote_path, and a registered board."""
    from deepgent.evals.replay import ReplayRecorder, list_fixtures

    if action == "list":
        fixtures = list_fixtures(Path.cwd())
        if not fixtures:
            return "no fixtures recorded"
        return "\n".join(f"{m.name}  {m.board}  {m.sha256[:12]}  {m.size_bytes}B" for m in fixtures)
    if action not in {"record", "replay"}:
        return f"error: unknown action '{action}'; use record, replay, or list"
    if not (name and board and command and remote_path):
        return "error: record/replay need name, board, command, and remote_path"
    try:
        recorder = ReplayRecorder(board, Path.cwd())
        if action == "record":
            m = await recorder.record(name, command, remote_path)
            return f"recorded {name} ({m.sha256[:12]}, {m.size_bytes}B)"
        exit_status, output = await recorder.replay(name, command, remote_path)
        return f"[exit {exit_status}]\n{output}"
    except _DeepgentError as exc:
        return f"error: {exc}"


async def bisect(task: str, good: str, bad: str) -> str:
    """Auto-bisect a regressed golden across commits between good and bad to the
    breaking change. Runs the golden as the predicate at each revision and
    restores the original branch afterward. Requires a git repo with the
    golden; on-target goldens also require a registered board."""
    import subprocess

    from deepgent.evals import run_golden
    from deepgent.evals.bisect import bisect as _bisect

    try:
        revs = subprocess.run(
            ["git", "rev-list", "--reverse", f"{good}..{bad}"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.split()
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        return f"error: cannot list commits {good}..{bad}: {exc}"
    candidates = [good, *revs]
    if candidates[-1] != bad:
        candidates.append(bad)
    if len(candidates) < 2:
        return f"error: no commits between {good} and {bad}"

    async def predicate(rev: str) -> bool:
        subprocess.run(["git", "checkout", "--quiet", rev], check=True)
        return (await run_golden(task, Path.cwd())).passed

    original = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True, text=True
    ).stdout.strip()
    try:
        result = await _bisect(candidates, predicate)
    except _DeepgentError as exc:
        return f"error: {exc}"
    finally:
        if original and original != "HEAD":
            subprocess.run(["git", "checkout", "--quiet", original], check=False)
    report = result.render_report()
    if result.first_bad:
        report += f"\nbreaking change: {result.first_bad}"
    return report


# --- on-target runners (need a registered board; error if unavailable) ------


def _run_dir(prefix: str):  # type: ignore[no-untyped-def]
    from deepgent.evals import create_run_dir

    return create_run_dir(prefix, Path.cwd())


async def profile_thermal(
    board: str, workload: str, hold: float = 60.0, modes: str = "", tj_max: float = 95.0
) -> str:
    """Sustained thermal/DVFS envelope on a board (burst vs sustained, thermal
    knee). Requires a registered board."""
    from deepgent.evals import parse_modes
    from deepgent.evals.thermal_envelope import ThermalEnvelopeProfiler

    try:
        mode_list = parse_modes(modes) if modes else None
        result = await ThermalEnvelopeProfiler(board, _run_dir(f"thermal-{board}")).run(
            workload, hold, mode_list, tj_ceiling_c=tj_max
        )
        return result.render_table()
    except _DeepgentError as exc:
        return f"error: {exc}"


async def profile_latency(
    board: str, command: str, budget_ms: float = 0.0, capture: float = 30.0
) -> str:
    """Glass-to-glass per-stage latency trace with a p99 budget gate. Requires a
    registered board."""
    from deepgent.evals.latency_trace import LatencyTracer

    try:
        trace = await LatencyTracer(board, _run_dir(f"latency-{board}")).run(
            command, budget_ms=budget_ms or None, capture_s=capture
        )
        return trace.render_report()
    except _DeepgentError as exc:
        return f"error: {exc}"


async def profile_nsight(board: str, command: str, capture: float = 120.0) -> str:
    """Classify the dominant bottleneck (compute/memory/sync/cpu) from an Nsight
    trace. Requires a registered board."""
    from deepgent.evals.nsight import NsightProfiler

    try:
        result = await NsightProfiler(board, _run_dir(f"nsight-{board}")).run(command, capture)
        return result.render()
    except _DeepgentError as exc:
        return f"error: {exc}"


async def cuda_check(
    board: str, run: str, build: str = "", tools: str = "memcheck,racecheck"
) -> str:
    """Run compute-sanitizer on a target and gate on memory/race errors.
    Requires a registered GPU board."""
    from deepgent.evals.cuda_check import CudaSanitizerRunner

    try:
        result = await CudaSanitizerRunner(board, _run_dir(f"cuda-{board}")).run(
            run, build or None, _csv(tools)
        )
        return result.render()
    except _DeepgentError as exc:
        return f"error: {exc}"


async def fleet(command: str, boards: str) -> str:
    """Run a benchmark across a fleet; build a compat+perf matrix. boards is a
    comma-separated list of registered board ids."""
    from deepgent.evals import FleetRunner, new_run_id

    try:
        result = await FleetRunner(new_run_id(), _run_dir("fleet")).run(command, _csv(boards))
        return result.render_table()
    except _DeepgentError as exc:
        return f"error: {exc}"


async def soak(board: str, hours: float, workload: str = "", tj_max: float = 95.0) -> str:
    """Endurance run with anomaly snapshots and a survival report. Requires a
    registered board."""
    from deepgent.evals.soak import AnomalyRules, SoakRunner, default_phases

    try:
        runner = SoakRunner(board, _run_dir(f"soak-{board}"), rules=AnomalyRules(tj_max_c=tj_max))
        result = await runner.run(default_phases(hours * 3600.0, workload or None))
        return result.render_report()
    except _DeepgentError as exc:
        return f"error: {exc}"


async def differential(artifact: str, boards: str, command: str) -> str:
    """Run one local artifact across boards and compare latency/power/energy.
    boards is a comma-separated list of registered board ids."""
    from deepgent.evals import create_run_dir
    from deepgent.evals.differential import DifferentialRunner

    try:
        runner = DifferentialRunner(Path.cwd())
        result = await runner.run(Path(artifact), _csv(boards), command)
        runner.persist(result, create_run_dir("differential", Path.cwd()))
        return result.render_table()
    except _DeepgentError as exc:
        return f"error: {exc}"


async def accuracy_gate(
    board: str,
    command: str,
    metric: str = "mAP",
    baseline: str = "",
    tolerance: float = 0.0,
    capture: float = 120.0,
) -> str:
    """Run an on-device eval and gate the metric against a baseline. The device
    must print 'METRIC <name> <value>'. Requires a registered board."""
    from deepgent.evals.accuracy import AccuracyGate, load_baseline

    try:
        base = load_baseline(baseline or None, metric)
        result = await AccuracyGate().run(board, command, metric, base, tolerance, capture)
        return result.render()
    except _DeepgentError as exc:
        return f"error: {exc}"


async def quant_sweep(
    board: str,
    command: str,
    precisions: str = "fp16,int8",
    batches: str = "1,2",
    devices: str = "gpu",
    accuracy_metric: str = "",
    capture: float = 30.0,
) -> str:
    """Sweep precision x batch x device on a board to a Pareto frontier.
    command is a template with {precision} {batch} {device}. Requires a board."""
    from deepgent.evals import expand_grid, knee, select_best
    from deepgent.evals.quant_sweep import QuantSweepRunner

    try:
        configs = expand_grid(_csv(precisions), [int(b) for b in _csv(batches)], _csv(devices))
        result = await QuantSweepRunner(board, _run_dir(f"quant-{board}")).run(
            command, configs, capture, accuracy_metric or None
        )
        best = select_best(result.frontier)
        eff = knee(result.frontier)
        return (
            result.render_table()
            + f"\nbest(min latency): {best.config.label if best else 'none'}"
            + f"\nknee(max fps/W): {eff.config.label if eff else 'none'}"
        )
    except _DeepgentError as exc:
        return f"error: {exc}"


async def select_model(
    board: str,
    manifest: str,
    max_power: float = 0.0,
    min_fps: float = 0.0,
    max_latency: float = 0.0,
    min_accuracy: float = 0.0,
    accuracy_metric: str = "",
    capture: float = 30.0,
) -> str:
    """Benchmark candidate models on a board and return those meeting a
    power/fps/latency/accuracy budget. manifest is a JSON array path or content."""
    from deepgent.evals.model_selector import Constraint, ModelSelector, load_candidates

    try:
        # load_candidates takes a path; write inline JSON to a temp if needed.
        path = Path(manifest)
        if not path.is_file():
            path = _run_dir(f"select-{board}") / "manifest.json"
            path.write_text(manifest)
        constraint = Constraint(
            max_power_w=max_power or None,
            min_fps=min_fps or None,
            max_latency_ms=max_latency or None,
            min_accuracy=min_accuracy or None,
        )
        result = await ModelSelector(board, _run_dir(f"select-{board}")).run(
            load_candidates(path), constraint, capture, accuracy_metric or None
        )
        return result.render_table()
    except _DeepgentError as exc:
        return f"error: {exc}"


async def run_task(task: str, budget: float = 0.5) -> str:
    """Run a full deepgent agent task to completion (writes/edits files, runs
    commands, reviews and tests). Costs API and modifies the working directory;
    only available when the server was started with --allow-task. budget is the
    per-task USD cap."""
    from deepgent.config import load_settings
    from deepgent.core import Orchestrator

    settings = load_settings().model_copy(update={"permission_mode": "acceptEdits"}, deep=True)
    settings.budget.per_task_usd = budget
    outcome = await Orchestrator(settings=settings, cwd=Path.cwd()).run_task(task)
    cost = f"${outcome.total_cost_usd:.4f}" if outcome.total_cost_usd is not None else "n/a"
    verdict = "error" if outcome.is_error else "ok"
    return f"[{verdict} | {outcome.num_turns} turns | {cost}]\n\n{outcome.result}"


# Deterministic, no-hardware, no-API: safe to expose everywhere.
_DETERMINISTIC = (
    hw_check,
    boards_catalog,
    matrix_query,
    matrix_analyze,
    accuracy_score,
    skills_eval,
    facts,
    reflect,
    generate_ros2_node,
    generate_systemd,
    errata_scan,
    bom_advise,
    host_doctor,
    host_profile,
    telemetry_summary,
    boards_list,
)

# Query the knowledge layer (RAG/matrix); degrade to a note when it is absent.
_KNOWLEDGE = (
    premortem,
    triage,
    upgrade_check,
    scaffold_driver,
)

# Execute on a registered target board over SSH; return an error if none is
# reachable. The board registry (deepgent boards add) is the access boundary.
_HARDWARE = (
    profile_thermal,
    profile_latency,
    profile_nsight,
    cuda_check,
    fleet,
    soak,
    differential,
    accuracy_gate,
    quant_sweep,
    select_model,
    shadow,
    replay,
    bisect,
)


def build_server(allow_task: bool = False) -> FastMCP:
    """Build the deepgent MCP server; allow_task adds the paid run_task tool."""
    server = FastMCP("deepgent")
    for fn in (*_DETERMINISTIC, *_KNOWLEDGE, *_HARDWARE):
        server.add_tool(fn)
    if allow_task:
        server.add_tool(run_task)
    return server


def bearer_guard(app: _ASGIApp, token: str) -> _ASGIApp:
    """Wrap an ASGI app to require 'Authorization: Bearer <token>' on HTTP.

    Pure ASGI (inspects only the request scope), so it is safe with the
    streaming SSE / streamable-http transports.
    """
    expected = f"Bearer {token}".encode()

    async def guarded(scope: Any, receive: Any, send: Any) -> None:
        if scope.get("type") == "http":
            headers = dict(scope.get("headers") or [])
            if headers.get(b"authorization") != expected:
                await send(
                    {
                        "type": "http.response.start",
                        "status": 401,
                        "headers": [(b"content-type", b"text/plain; charset=utf-8")],
                    }
                )
                await send({"type": "http.response.body", "body": b"unauthorized"})
                return
        await app(scope, receive, send)

    return guarded


def serve(
    server: FastMCP,
    transport: str = "stdio",
    host: str = "127.0.0.1",
    port: int = 8000,
    token: str | None = None,
) -> None:
    """Run the server. stdio owns the process's stdio; http/sse bind host:port
    and, when a token is given, require a bearer token (for remote connectors)."""
    if transport == "stdio":
        server.run("stdio")
        return
    server.settings.host = host
    server.settings.port = port
    app: _ASGIApp = server.sse_app() if transport == "sse" else server.streamable_http_app()
    if token:
        app = bearer_guard(app, token)
    import uvicorn

    uvicorn.run(app, host=host, port=port, log_level="warning")
