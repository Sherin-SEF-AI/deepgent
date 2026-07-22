"""CLI entry points (section 15 contract, WO-2 subset).

Implemented: `deepgent "<task>"`, `deepgent init`, `deepgent doctor`,
`deepgent --version`. The remaining surface arrives with later work orders.
"""

import asyncio
import importlib.metadata
import logging
import os
import platform
import shutil
import sys
from pathlib import Path
from typing import Any

import structlog
import typer

# typer >= 0.27 vendors click; subclassing TyperGroup requires its types.
from typer._click.core import Command, Context
from typer._click.exceptions import UsageError
from typer.core import TyperGroup

import deepgent
from deepgent.boards import (
    BoardConfig,
    BoardRunner,
    add_board,
    get_board,
    load_registry,
    registry_path,
    remove_board,
)
from deepgent.config import load_settings
from deepgent.containers import ContainerBuilder, load_jp6_spec
from deepgent.containers.build import BINFMT_FLAG
from deepgent.core import Orchestrator
from deepgent.errors import DeepgentError
from deepgent.evals import run_golden
from deepgent.knowledge import build_rag_client, default_skills_dir, list_skills


class DeepgentGroup(TyperGroup):
    """Dispatches unknown first tokens to the one-shot task command, so
    `deepgent "<task>"` works alongside subcommands (section 15)."""

    def resolve_command(
        self, ctx: Context, args: list[str]
    ) -> tuple[str | None, Command | None, list[str]]:
        try:
            return super().resolve_command(ctx, args)
        except UsageError:
            task_cmd = self.get_command(ctx, "task")
            if task_cmd is None:
                raise
            return task_cmd.name, task_cmd, args


app = typer.Typer(add_completion=False, cls=DeepgentGroup)
containers_app = typer.Typer(help="Build and verify toolchain containers.")
app.add_typer(containers_app, name="containers")
boards_app = typer.Typer(help="Manage the target board registry.")
app.add_typer(boards_app, name="boards")
evals_app = typer.Typer(help="Run golden tasks and score them mechanically.")
app.add_typer(evals_app, name="evals")
skills_app = typer.Typer(help="Inspect local skill packs.")
app.add_typer(skills_app, name="skills")
rag_app = typer.Typer(help="Datasheet RAG operations (owner/server mode).")
app.add_typer(rag_app, name="rag")

_PROJECT_MD = """\
# deepgent project state

Maintained by deepgent; updated after every task. Human-readable summary of
goals, decisions, and hardware context for this repository.

## Hardware targets

None recorded yet. Run tasks with --board, or `deepgent boards add`, to
populate this section.

## Task history

No tasks run yet.
"""

_PROJECT_CONFIG = """\
# deepgent project configuration. Values here override ~/.deepgent/config.toml;
# DEEPGENT_ environment variables override both.

# default_board = "agx-orin"

[budget]
per_task_usd = 2.00
"""


def _configure_logging(debug: bool) -> None:
    level = logging.DEBUG if debug else logging.INFO
    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(sys.stderr),
    )


def _fail(message: str, *, debug: bool, exc: Exception | None = None) -> None:
    if debug and exc is not None:
        raise exc
    typer.secho(f"error: {message}", err=True, fg=typer.colors.RED)
    raise typer.Exit(code=1)


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: bool = typer.Option(False, "--version", help="Print the deepgent version and exit."),
) -> None:
    """deepgent: autonomous engineering agent for AV, CV, and embedded systems."""
    if version:
        typer.echo(f"deepgent {deepgent.__version__}")
        raise typer.Exit()
    if ctx.invoked_subcommand is None:
        # Interactive sessions arrive with a later work order.
        typer.echo(ctx.get_help())
        raise typer.Exit()


@app.command(name="task", hidden=True)
def run_one_shot(
    task: str = typer.Argument(..., help="Natural-language engineering task to run."),
    debug: bool = typer.Option(False, "--debug", help="Show raw tracebacks and debug logs."),
) -> None:
    """Run a single task to completion (also reachable as `deepgent "<task>"`)."""
    _configure_logging(debug)
    try:
        settings = load_settings()
        orchestrator = Orchestrator(settings=settings, cwd=Path.cwd())
        outcome = asyncio.run(orchestrator.run_task(task))
    except DeepgentError as exc:
        _fail(str(exc), debug=debug, exc=exc)
        return
    typer.echo(outcome.result)
    if outcome.total_cost_usd is not None:
        typer.secho(
            f"[{outcome.num_turns} turns, ${outcome.total_cost_usd:.2f}]",
            err=True,
            fg=typer.colors.BLUE,
        )
    raise typer.Exit(code=1 if outcome.is_error else 0)


@containers_app.command("build")
def containers_build(
    target: str = typer.Argument("jp6", help="Container target to build."),
    smoke: bool = typer.Option(
        False, "--smoke", help="Run the CUDA compile smoke check after building."
    ),
    debug: bool = typer.Option(False, "--debug", help="Show raw tracebacks."),
) -> None:
    """Build a version-pinned toolchain container (linux/arm64 via qemu)."""
    _configure_logging(debug)
    if target != "jp6":
        _fail(f"unknown container target '{target}'; available: jp6", debug=debug)
    try:
        builder = ContainerBuilder(load_jp6_spec())
        builder.build()
        if smoke:
            builder.cuda_smoke()
    except DeepgentError as exc:
        _fail(str(exc), debug=debug, exc=exc)
        return
    typer.secho(f"built {builder.spec.image_tag}", fg=typer.colors.GREEN)
    if smoke:
        typer.secho("CUDA smoke check passed (aarch64 ELF)", fg=typer.colors.GREEN)


@boards_app.command("add")
def boards_add(
    board_id: str = typer.Argument(..., help="Board id, e.g. agx-orin."),
    host: str = typer.Option(..., "--host", help="Hostname or IP of the board."),
    ssh_user: str = typer.Option(..., "--user", help="SSH user on the board."),
    key_path: Path = typer.Option(..., "--key", help="Path to the per-board SSH private key."),
    board_type: str = typer.Option(..., "--type", help="Board type, e.g. jetson-agx-orin."),
    l4t: str | None = typer.Option(None, "--l4t", help="L4T version on the board."),
    capabilities: str = typer.Option(
        "", "--capabilities", help="Comma-separated capabilities (csi,can,gpio,hailo)."
    ),
    power_ctl: str = typer.Option("none", "--power-ctl", help="none, smartplug, or pdu."),
    debug: bool = typer.Option(False, "--debug", help="Show raw tracebacks."),
) -> None:
    """Register a board in ~/.deepgent/boards.toml."""
    caps = [c.strip() for c in capabilities.split(",") if c.strip()]
    try:
        board = BoardConfig(
            id=board_id,
            host=host,
            ssh_user=ssh_user,
            key_path=key_path,
            type=board_type,
            l4t=l4t,
            capabilities=caps,
            power_ctl=power_ctl,  # type: ignore[arg-type]
        )
        add_board(board)
    except (DeepgentError, ValueError) as exc:
        _fail(str(exc), debug=debug, exc=exc if isinstance(exc, DeepgentError) else None)
        return
    typer.secho(f"registered board '{board_id}' in {registry_path()}", fg=typer.colors.GREEN)


@boards_app.command("list")
def boards_list() -> None:
    """List registered boards."""
    boards = load_registry()
    if not boards:
        typer.echo(
            f"no boards registered; add one with: deepgent boards add (see {registry_path()})"
        )
        return
    for board in boards.values():
        caps = ",".join(board.capabilities) or "-"
        typer.echo(
            f"{board.id}  {board.ssh_user}@{board.host}  type={board.type}  "
            f"l4t={board.l4t or '-'}  caps={caps}  power={board.power_ctl}"
        )


@boards_app.command("test")
def boards_test(
    board_id: str = typer.Argument(..., help="Board id to test."),
    debug: bool = typer.Option(False, "--debug", help="Show raw tracebacks."),
) -> None:
    """Connect to a board and verify it answers."""
    _configure_logging(debug)

    async def _probe() -> str:
        board = get_board(board_id)
        async with BoardRunner(board) as runner:
            result = await runner.run("uname -m && uname -r", timeout_s=15)
            if result.exit_status != 0:
                raise DeepgentError(
                    f"probe command failed on '{board_id}' "
                    f"(exit {result.exit_status}): {result.stderr.strip()}"
                )
            return result.stdout.strip()

    try:
        answer = asyncio.run(_probe())
    except DeepgentError as exc:
        _fail(str(exc), debug=debug, exc=exc)
        return
    typer.secho(f"board '{board_id}' ok: {answer.replace(chr(10), ' / ')}", fg=typer.colors.GREEN)


@boards_app.command("remove")
def boards_remove(
    board_id: str = typer.Argument(..., help="Board id to remove."),
    debug: bool = typer.Option(False, "--debug", help="Show raw tracebacks."),
) -> None:
    """Remove a board from the registry."""
    try:
        remove_board(board_id)
    except DeepgentError as exc:
        _fail(str(exc), debug=debug, exc=exc)
        return
    typer.echo(f"removed board '{board_id}'")


@evals_app.command("run")
def evals_run(
    task: str = typer.Option(..., "--task", help="Golden task id, e.g. gt-0001."),
    diff: bool = typer.Option(
        False, "--diff", help="Compare against the recorded baseline (regression gate)."
    ),
    update_baseline: bool = typer.Option(
        False, "--update-baseline", help="Record this run as the new baseline."
    ),
    debug: bool = typer.Option(False, "--debug", help="Show raw tracebacks."),
) -> None:
    """Run one golden task and score it mechanically."""
    from deepgent.evals.runner import diff_against_baseline
    from deepgent.evals.runner import update_baseline as save_baseline

    _configure_logging(debug)
    try:
        result = asyncio.run(run_golden(task, Path.cwd()))
    except DeepgentError as exc:
        _fail(str(exc), debug=debug, exc=exc)
        return
    for criterion in result.criteria:
        color = typer.colors.GREEN if criterion.passed else typer.colors.RED
        typer.secho(criterion.describe(), fg=color)
    typer.echo(f"artifacts: {result.run_dir}")
    failed = not result.passed
    if diff:
        findings = diff_against_baseline(result, Path.cwd())
        for finding in findings:
            typer.secho(finding, fg=typer.colors.RED)
            failed = True
    if update_baseline:
        save_baseline(result, Path.cwd())
        typer.echo(f"baseline updated for {task}")
    if failed:
        typer.secho(f"{task} FAILED", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    typer.secho(f"{task} PASSED", fg=typer.colors.GREEN)


@app.command("bisect")
def bisect_cmd(
    task: str = typer.Option(..., "--task", help="Golden task id to use as the predicate."),
    good: str = typer.Option(..., "--good", help="Known-good git ref."),
    bad: str = typer.Option(..., "--bad", help="Known-bad git ref."),
    debug: bool = typer.Option(False, "--debug", help="Show raw tracebacks."),
) -> None:
    """Auto-bisect a regressed golden across commits to the breaking change (Tier 1)."""
    import subprocess

    from deepgent.evals import run_golden
    from deepgent.evals.bisect import bisect as run_bisect

    _configure_logging(debug)
    try:
        revs = subprocess.run(
            ["git", "rev-list", "--reverse", f"{good}..{bad}"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.split()
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        _fail(f"cannot list commits {good}..{bad}: {exc}", debug=debug)
        return
    candidates = [good, *revs]
    if candidates[-1] != bad:
        candidates.append(bad)
    if len(candidates) < 2:
        _fail(f"no commits between {good} and {bad}", debug=debug)

    async def predicate(rev: str) -> bool:
        subprocess.run(["git", "checkout", "--quiet", rev], check=True)
        result = await run_golden(task, Path.cwd())
        return result.passed

    original = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True, text=True
    ).stdout.strip()
    try:
        result = asyncio.run(run_bisect(candidates, predicate))
    except DeepgentError as exc:
        _fail(str(exc), debug=debug, exc=exc)
        return
    finally:
        if original and original != "HEAD":
            subprocess.run(["git", "checkout", "--quiet", original], check=False)
    typer.echo(result.render_report())
    if result.first_bad:
        typer.secho(f"breaking change: {result.first_bad}", fg=typer.colors.RED)


@app.command("replay")
def replay_cmd(
    action: str = typer.Argument(..., help="record | replay | list"),
    name: str = typer.Option("", "--name", help="Fixture name."),
    board: str = typer.Option("", "--board", help="Registered board id."),
    command: str = typer.Option("", "--command", help="Record or replay command."),
    remote_path: str = typer.Option("", "--remote-path", help="Board-side stream path."),
    debug: bool = typer.Option(False, "--debug", help="Show raw tracebacks."),
) -> None:
    """Record real sensor streams as fixtures and replay them (Tier 1)."""
    from deepgent.evals.replay import ReplayRecorder, list_fixtures

    _configure_logging(debug)
    if action == "list":
        for manifest in list_fixtures(Path.cwd()):
            typer.echo(
                f"{manifest.name}  {manifest.board}  {manifest.sha256[:12]}  {manifest.size_bytes}B"
            )
        return
    if action not in {"record", "replay"}:
        _fail(f"unknown replay action '{action}'; use record, replay, or list", debug=debug)
    if not (name and board and command and remote_path):
        _fail("record/replay need --name, --board, --command, and --remote-path", debug=debug)
    try:
        recorder = ReplayRecorder(board, Path.cwd())
        if action == "record":
            manifest = asyncio.run(recorder.record(name, command, remote_path))
            typer.secho(
                f"recorded {name} ({manifest.sha256[:12]}, {manifest.size_bytes}B)",
                fg=typer.colors.GREEN,
            )
        else:
            exit_status, output = asyncio.run(recorder.replay(name, command, remote_path))
            typer.echo(output)
            raise typer.Exit(code=1 if exit_status != 0 else 0)
    except DeepgentError as exc:
        _fail(str(exc), debug=debug, exc=exc)


@app.command("differential")
def differential_cmd(
    artifact: Path = typer.Argument(..., help="Local artifact to run on each board."),
    boards: str = typer.Option(..., "--boards", help="Comma-separated board ids."),
    command: str = typer.Option(
        ..., "--command", help="Command to run the artifact on each board."
    ),
    debug: bool = typer.Option(False, "--debug", help="Show raw tracebacks."),
) -> None:
    """Run one artifact across boards and compare latency/power/energy (Tier 3)."""
    from deepgent.evals import create_run_dir
    from deepgent.evals.differential import DifferentialRunner

    _configure_logging(debug)
    board_ids = [b.strip() for b in boards.split(",") if b.strip()]
    try:
        runner = DifferentialRunner(Path.cwd())
        result = asyncio.run(runner.run(artifact, board_ids, command))
        run_dir = create_run_dir("differential", Path.cwd())
        runner.persist(result, run_dir)
    except DeepgentError as exc:
        _fail(str(exc), debug=debug, exc=exc)
        return
    typer.echo(result.render_table())
    typer.echo(f"artifacts: {run_dir}")


@app.command("soak")
def soak_run(
    board: str = typer.Option(..., "--board", help="Registered board id."),
    hours: float = typer.Option(..., "--hours", min=0.01, help="Planned soak duration."),
    workload: str | None = typer.Option(
        None, "--workload", help="Remote workload command; omit for pure observation."
    ),
    tj_max: float = typer.Option(95.0, "--tj-max", help="Thermal anomaly ceiling in C."),
    debug: bool = typer.Option(False, "--debug", help="Show raw tracebacks."),
) -> None:
    """Endurance run with anomaly snapshots and a survival report (Tier 1)."""
    from deepgent.evals import create_run_dir
    from deepgent.evals.soak import AnomalyRules, SoakRunner, default_phases

    _configure_logging(debug)
    try:
        run_dir = create_run_dir(f"soak-{board}", Path.cwd())
        runner = SoakRunner(board, run_dir, rules=AnomalyRules(tj_max_c=tj_max))
        phases = default_phases(hours * 3600.0, workload)
        result = asyncio.run(runner.run(phases))
    except DeepgentError as exc:
        _fail(str(exc), debug=debug, exc=exc)
        return
    typer.echo(result.render_report())
    typer.echo(f"artifacts: {run_dir}")
    raise typer.Exit(code=0 if result.survived else 1)


@app.command("ci")
def ci_run(
    task: str = typer.Option(..., "--task", help="Task to run non-interactively."),
    budget: float | None = typer.Option(None, "--budget", help="Per-task budget cap in USD."),
) -> None:
    """Non-interactive CI mode: JSON to stdout, exit code is pass/fail,
    gated board operations auto-deny unless whitelisted (section 15)."""
    import json as json_module

    _configure_logging(False)
    try:
        settings = load_settings().model_copy(update={"ci": True}, deep=True)
        if budget is not None:
            settings.budget.per_task_usd = budget
        orchestrator = Orchestrator(settings=settings, cwd=Path.cwd())
        outcome = asyncio.run(orchestrator.run_task(task))
    except DeepgentError as exc:
        typer.echo(json_module.dumps({"ok": False, "error": str(exc)}))
        raise typer.Exit(code=1) from None
    typer.echo(
        json_module.dumps(
            {
                "ok": not outcome.is_error,
                "result": outcome.result,
                "session_id": outcome.session_id,
                "num_turns": outcome.num_turns,
                "total_cost_usd": outcome.total_cost_usd,
            }
        )
    )
    raise typer.Exit(code=1 if outcome.is_error else 0)


@app.command("versions-check", hidden=True)
def versions_check(
    debug: bool = typer.Option(False, "--debug", help="Show raw tracebacks."),
) -> None:
    """Check upstream release feeds against versions.toml (release watch)."""
    from deepgent.containers import load_jp6_spec
    from deepgent.knowledge.release_watch import check_releases

    _configure_logging(debug)
    try:
        findings = check_releases(load_jp6_spec().l4t_container)
    except DeepgentError as exc:
        _fail(str(exc), debug=debug, exc=exc)
        return
    if not findings:
        typer.secho("versions.toml is current with upstream", fg=typer.colors.GREEN)
        return
    for finding in findings:
        typer.echo(finding.describe())
    raise typer.Exit(code=3)


@rag_app.command("ingest")
def rag_ingest(
    file: Path = typer.Argument(..., help="Public datasheet file (PDF, text, or markdown)."),
    chip: str = typer.Option(..., "--chip", help="Chip the document applies to."),
    l4t: str = typer.Option("*", "--l4t", help="Applicable L4T/JetPack range."),
    debug: bool = typer.Option(False, "--debug", help="Show raw tracebacks."),
) -> None:
    """Chunk a public datasheet and ingest it into the knowledge API."""
    _configure_logging(debug)
    if not file.is_file():
        _fail(f"{file} does not exist", debug=debug)
    try:
        # Chunking runs server-side conceptually; the owner CLI imports the
        # server package (workspace member) to prepare chunks locally.
        from deepgent_server.ingest import chunk_file

        settings = load_settings()
        client = build_rag_client(settings)

        async def _ingest() -> int:
            count = 0
            try:
                for raw in chunk_file(file):
                    await client.ingest(
                        doc=file.name,
                        chip=chip,
                        version_range=l4t,
                        section=raw.section,
                        text=raw.text,
                    )
                    count += 1
            finally:
                await client.aclose()
            return count

        ingested = asyncio.run(_ingest())
    except ImportError:
        _fail(
            "the server package is not installed; run: uv sync --all-groups "
            "(rag ingest is owner/server mode)",
            debug=debug,
        )
        return
    except DeepgentError as exc:
        _fail(str(exc), debug=debug, exc=exc)
        return
    typer.secho(f"ingested {ingested} chunk(s) from {file.name}", fg=typer.colors.GREEN)


@rag_app.command("search")
def rag_search(
    query: str = typer.Argument(..., help="Hardware question to search for."),
    chip: str | None = typer.Option(None, "--chip", help="Restrict to one chip."),
    debug: bool = typer.Option(False, "--debug", help="Show raw tracebacks."),
) -> None:
    """Search the knowledge API and print chunks with provenance."""
    _configure_logging(debug)
    try:
        settings = load_settings()
        client = build_rag_client(settings)

        async def _search() -> list[dict[str, Any]]:
            try:
                return await client.search(query, chip=chip)
            finally:
                await client.aclose()

        chunks = asyncio.run(_search())
    except DeepgentError as exc:
        _fail(str(exc), debug=debug, exc=exc)
        return
    if not chunks:
        typer.echo("unknown: no provenanced chunks matched")
        return
    for chunk in chunks:
        typer.secho(
            f"[{chunk['doc']} / {chunk['section']} / {chunk['chip']} / "
            f"l4t {chunk['version_range']}] (id {chunk['id']})",
            fg=typer.colors.BLUE,
        )
        typer.echo(chunk["text"][:400])
        typer.echo("")


@rag_app.command("triage")
def rag_triage(
    symptom: str = typer.Argument(..., help="Failure symptom text."),
    hw: str | None = typer.Option(None, "--hw", help="Hardware config filter."),
    debug: bool = typer.Option(False, "--debug", help="Show raw tracebacks."),
) -> None:
    """Corpus-first debugging: check the failure corpus before any LLM call (Tier 2)."""
    from deepgent.knowledge import triage as run_triage

    _configure_logging(debug)
    try:
        settings = load_settings()
        client = build_rag_client(settings)

        async def _go() -> Any:
            try:
                return await run_triage(client, symptom, hw=hw)
            finally:
                await client.aclose()

        result = asyncio.run(_go())
    except DeepgentError as exc:
        _fail(str(exc), debug=debug, exc=exc)
        return
    typer.echo(result.render())
    raise typer.Exit(code=0 if result.corpus_hit else 2)


@rag_app.command("upgrade-check")
def rag_upgrade_check(
    component: str = typer.Argument(..., help="Stack component, e.g. trt."),
    to_version: str = typer.Argument(..., help="Proposed new version."),
    debug: bool = typer.Option(False, "--debug", help="Show raw tracebacks."),
) -> None:
    """Verified impact report for a proposed version move (Tier 2)."""
    from deepgent.config import load_versions
    from deepgent.knowledge import upgrade_check

    _configure_logging(debug)
    try:
        versions = load_versions()
        jp6 = versions["jetson"]["jp6"]
        current = {
            "l4t": str(jp6["l4t"]),
            "cuda": str(jp6["cuda"]),
            "trt": str(jp6["tensorrt"]),
        }
        settings = load_settings()
        client = build_rag_client(settings)

        async def _go() -> Any:
            try:
                return await upgrade_check(client, current, {component: to_version})
            finally:
                await client.aclose()

        report = asyncio.run(_go())
    except DeepgentError as exc:
        _fail(str(exc), debug=debug, exc=exc)
        return
    except KeyError as exc:
        _fail(f"versions.toml [jetson.jp6] missing key {exc}", debug=debug)
        return
    typer.echo(report.render())
    raise typer.Exit(code=0 if report.safe else 1)


@app.command("scaffold-driver")
def scaffold_driver_cmd(
    device: str = typer.Argument(..., help="Device name, e.g. 'IMX219 Camera'."),
    compatible: str = typer.Option(..., "--compatible", help="DT compatible string."),
    chip: str = typer.Option(..., "--chip", help="Chip to search datasheet-rag for."),
    kind: str = typer.Option("i2c", "--kind", help="i2c or v4l2."),
    debug: bool = typer.Option(False, "--debug", help="Show raw tracebacks."),
) -> None:
    """Scaffold a RAG-grounded driver skeleton + DT fragment (Tier 3)."""
    from deepgent.generators import scaffold_driver, spec_from_chunks

    _configure_logging(debug)
    try:
        settings = load_settings()
        client = build_rag_client(settings)

        async def _chunks() -> Any:
            try:
                return await client.search(f"{device} registers i2c address", chip=chip)
            finally:
                await client.aclose()

        chunks = asyncio.run(_chunks())
    except DeepgentError as exc:
        _fail(str(exc), debug=debug, exc=exc)
        return
    spec = spec_from_chunks(device, compatible, kind, chunks)
    output = scaffold_driver(spec)
    written = output.write(Path.cwd())
    for path in written:
        typer.echo(f"wrote {path}")
    for todo in output.todos:
        typer.secho(f"TODO: {todo}", fg=typer.colors.YELLOW)


@app.command("errata-scan")
def errata_scan_cmd(
    chips: str = typer.Option(..., "--chips", help="Comma-separated BOM chip ids."),
    errata_file: Path = typer.Option(..., "--errata", help="Errata definitions JSON file."),
    debug: bool = typer.Option(False, "--debug", help="Show raw tracebacks."),
) -> None:
    """Scan the codebase for patterns from errata affecting BOM chips (Tier 2)."""
    import json as json_module

    from deepgent.knowledge import Erratum, scan_errata

    _configure_logging(debug)
    if not errata_file.is_file():
        _fail(f"{errata_file} does not exist", debug=debug)
    entries = json_module.loads(errata_file.read_text())
    errata = [
        Erratum(
            id=e["id"],
            chip=e["chip"],
            title=e.get("title", ""),
            patterns=tuple(e["patterns"]),
            advisory=e.get("advisory", ""),
        )
        for e in entries
    ]
    bom = {c.strip() for c in chips.split(",") if c.strip()}
    result = scan_errata(Path.cwd(), errata, bom)
    typer.echo(result.render_advisory())
    raise typer.Exit(code=1 if result.exposed else 0)


@skills_app.command("list")
def skills_list(
    debug: bool = typer.Option(False, "--debug", help="Show raw tracebacks."),
) -> None:
    """List locally available skill packs."""
    try:
        packs = list_skills()
    except DeepgentError as exc:
        _fail(str(exc), debug=debug, exc=exc)
        return
    if not packs:
        source = default_skills_dir()
        typer.echo(
            "no skill packs found"
            + (f" in {source}" if source else " (no local skills source resolved)")
        )
        return
    for pack in packs:
        typer.echo(f"{pack.name}  {pack.description}")


@app.command()
def init(
    directory: Path = typer.Argument(Path("."), help="Project directory to initialize."),
) -> None:
    """Initialize .deepgent/ project state in the given directory."""
    target = directory / ".deepgent"
    target.mkdir(parents=True, exist_ok=True)
    created = []
    for name, content in [
        ("project.md", _PROJECT_MD),
        ("config.toml", _PROJECT_CONFIG),
    ]:
        path = target / name
        if path.exists():
            typer.echo(f"kept existing {path}")
        else:
            path.write_text(content)
            created.append(path)
    for path in created:
        typer.echo(f"created {path}")
    if not created:
        typer.echo("already initialized")


@app.command()
def report(
    run_id: str | None = typer.Argument(None, help="Task/session id; omit for recent tasks."),
    debug: bool = typer.Option(False, "--debug", help="Show raw tracebacks."),
) -> None:
    """Show task telemetry: tokens, cost, loops, and outcomes (section 9)."""
    from deepgent.telemetry import TelemetryStore

    _configure_logging(debug)
    store = TelemetryStore()
    if run_id is not None:
        record = store.get_task(run_id)
        if record is None:
            _fail(f"no task record with id '{run_id}'", debug=debug)
            return
        typer.echo(f"id:        {record.id}")
        typer.echo(f"class:     {record.task_class}")
        typer.echo(f"board:     {record.board or '-'}")
        typer.echo(f"outcome:   {record.outcome}")
        typer.echo(f"loops:     {record.loops}")
        typer.echo(f"tokens:    {record.tokens}")
        typer.echo(f"usd:       {record.usd if record.usd is not None else '-'}")
        typer.echo(f"wall_s:    {record.wall_s:.1f}")
        typer.echo(f"model_mix: {record.model_mix}")
        if record.failure_tag:
            typer.echo(f"failure:   {record.failure_tag}")
        return
    records = store.task_records()
    if not records:
        typer.echo("no task records yet; run a task first")
        return
    for record in records:
        usd = f"${record.usd:.2f}" if record.usd is not None else "-"
        typer.echo(
            f"{record.id}  {record.outcome:7s}  loops={record.loops:<3d} "
            f"tokens={record.tokens:<8d} {usd:>7s}  {record.wall_s:6.1f}s"
        )


@app.command()
def doctor(
    debug: bool = typer.Option(False, "--debug", help="Show raw tracebacks on check failures."),
) -> None:
    """Check that the environment can run deepgent tasks."""
    _configure_logging(debug)
    failures = 0

    def report(name: str, ok: bool, detail: str) -> None:
        nonlocal failures
        if not ok:
            failures += 1
        mark = (
            typer.style("ok  ", fg=typer.colors.GREEN)
            if ok
            else typer.style("FAIL", fg=typer.colors.RED)
        )
        typer.echo(f"{mark} {name}: {detail}")

    py = sys.version_info
    report(
        "python",
        py >= (3, 12),
        f"{py.major}.{py.minor}.{py.micro} (need >= 3.12)",
    )

    uv_path = shutil.which("uv")
    report("uv", uv_path is not None, uv_path or "not on PATH; install from astral.sh/uv")

    docker_path = shutil.which("docker")
    report(
        "docker",
        docker_path is not None,
        docker_path or "not on PATH; install Docker Engine (docs.docker.com/engine/install)",
    )

    native_arm = platform.machine() in ("aarch64", "arm64")
    binfmt_ok = native_arm or BINFMT_FLAG.exists()
    if native_arm:
        binfmt_detail = "native arm64 host"
    elif binfmt_ok:
        binfmt_detail = str(BINFMT_FLAG)
    else:
        binfmt_detail = (
            "not registered; run: docker run --privileged --rm tonistiigi/binfmt --install arm64"
        )
    report("qemu binfmt (arm64)", binfmt_ok, binfmt_detail)

    try:
        settings = load_settings()
    except DeepgentError as exc:
        report("versions.toml", False, str(exc))
    else:
        report(
            "versions.toml",
            True,
            f"model tiers: opus={settings.models.opus}, "
            f"sonnet={settings.models.sonnet}, haiku={settings.models.haiku}",
        )

    try:
        sdk_version = importlib.metadata.version("claude-agent-sdk")
    except importlib.metadata.PackageNotFoundError:
        report("claude-agent-sdk", False, "not installed; run uv sync")
    else:
        report("claude-agent-sdk", True, sdk_version)

    has_key = bool(os.environ.get("ANTHROPIC_API_KEY"))
    report(
        "api key",
        has_key,
        "ANTHROPIC_API_KEY is set"
        if has_key
        else "ANTHROPIC_API_KEY is not set; export it or configure the OS keyring",
    )

    if failures:
        typer.secho(f"{failures} check(s) failed", err=True, fg=typer.colors.RED)
        raise typer.Exit(code=1)
    typer.secho("all checks passed", fg=typer.colors.GREEN)
