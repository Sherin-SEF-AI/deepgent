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

_ASGIApp = Callable[[Any, Any, Any], Awaitable[None]]


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


_DETERMINISTIC = (
    hw_check,
    boards_catalog,
    matrix_query,
    matrix_analyze,
    accuracy_score,
    skills_eval,
    facts,
    reflect,
)


def build_server(allow_task: bool = False) -> FastMCP:
    """Build the deepgent MCP server; allow_task adds the paid run_task tool."""
    server = FastMCP("deepgent")
    for fn in _DETERMINISTIC:
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
