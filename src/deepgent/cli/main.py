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

import structlog
import typer

# typer >= 0.27 vendors click; subclassing TyperGroup requires its types.
from typer._click.core import Command, Context
from typer._click.exceptions import UsageError
from typer.core import TyperGroup

import deepgent
from deepgent.config import load_settings
from deepgent.containers import ContainerBuilder, load_jp6_spec
from deepgent.containers.build import BINFMT_FLAG
from deepgent.core import Orchestrator
from deepgent.errors import DeepgentError


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
