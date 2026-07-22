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
    debug: bool = typer.Option(False, "--debug", help="Show raw tracebacks."),
) -> None:
    """Run one golden task and score it mechanically."""
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
    if result.passed:
        typer.secho(f"{task} PASSED", fg=typer.colors.GREEN)
        return
    typer.secho(f"{task} FAILED", fg=typer.colors.RED)
    raise typer.Exit(code=1)


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
