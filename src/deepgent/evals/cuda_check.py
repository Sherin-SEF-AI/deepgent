"""CUDA memory and race safety gate via compute-sanitizer (#5).

The GPU analog of misra_gate: compile a target and run it under
compute-sanitizer on a board, parsing memcheck/racecheck/synccheck/initcheck
reports into structured errors and failing the gate on any. Custom kernels
ship gated, not on trust.

compute-sanitizer is dynamic (it needs a GPU and a compiled binary), so this
is a command run in the verify/hardware step, not an inline dev-host hook; the
cuda_gate hook only reminds that a modified kernel still needs this check.
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import structlog

from deepgent.boards import BoardRunner, LocalRunner, get_board, open_runner
from deepgent.errors import BoardError

_Runner = BoardRunner | LocalRunner
_logger = structlog.get_logger(__name__)

SANITIZER_TOOLS = ("memcheck", "racecheck", "synccheck", "initcheck")

# compute-sanitizer prints "========= <message>" lines; error summaries read
# "ERROR SUMMARY: N errors" (memcheck/synccheck/initcheck) or
# "RACECHECK SUMMARY: N hazards displayed" (racecheck).
_ERROR_SUMMARY = re.compile(r"=+\s*ERROR SUMMARY:\s*(\d+)\s+error", re.IGNORECASE)
_RACE_SUMMARY = re.compile(r"=+\s*RACECHECK SUMMARY:\s*(\d+)\s+hazard", re.IGNORECASE)
# Error headers, e.g. "========= Invalid __global__ read of size 4 bytes".
_ERROR_HEADER = re.compile(r"=+\s+((?:Invalid|Race|Uninitialized|Barrier|Misaligned|Fatal)\b.*)$")


@dataclass(frozen=True)
class SanitizerError:
    """One error extracted from a compute-sanitizer report."""

    tool: str
    detail: str

    def describe(self) -> str:
        return f"[{self.tool}] {self.detail}"


@dataclass
class CudaCheckResult:
    """Aggregate result across the sanitizer tools that were run."""

    errors: list[SanitizerError] = field(default_factory=list)
    summaries: dict[str, int] = field(default_factory=dict)

    @property
    def clean(self) -> bool:
        return not self.errors and all(count == 0 for count in self.summaries.values())

    def to_dict(self) -> dict[str, object]:
        return {
            "clean": self.clean,
            "summaries": self.summaries,
            "errors": [{"tool": e.tool, "detail": e.detail} for e in self.errors],
        }

    def render(self) -> str:
        lines = ["# cuda safety check (compute-sanitizer)"]
        for tool, count in self.summaries.items():
            lines.append(f"  {tool:<10} {count} issue(s)")
        if self.errors:
            lines.append("")
            lines.append("errors:")
            lines += [f"  - {e.describe()}" for e in self.errors[:50]]
        lines.append("")
        lines.append(f"result: {'CLEAN' if self.clean else 'FAIL'}")
        return "\n".join(lines) + "\n"

    def persist(self, run_dir: Path) -> None:
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "cuda-check.json").write_text(json.dumps(self.to_dict(), indent=2))
        (run_dir / "cuda-check.txt").write_text(self.render())


def parse_sanitizer_report(tool: str, output: str) -> tuple[list[SanitizerError], int]:
    """Extract errors and the summary count from one tool's report."""
    errors = [
        SanitizerError(tool=tool, detail=match.group(1).strip())
        for line in output.splitlines()
        if (match := _ERROR_HEADER.search(line))
    ]
    count = 0
    summary = _ERROR_SUMMARY.search(output) or _RACE_SUMMARY.search(output)
    if summary:
        count = int(summary.group(1))
    elif errors:
        count = len(errors)
    return errors, count


def sanitizer_command(tool: str, run_command: str) -> str:
    """compute-sanitizer invocation for one tool."""
    return f"compute-sanitizer --tool {tool} {run_command}"


class CudaSanitizerRunner:
    """Builds and runs a target under compute-sanitizer on a board."""

    def __init__(self, board_id: str, run_dir: Path) -> None:
        self._board_id = board_id
        self._run_dir = run_dir

    async def run(
        self,
        run_command: str,
        build_command: str | None = None,
        tools: list[str] | None = None,
        timeout_s: float = 300.0,
    ) -> CudaCheckResult:
        selected = tools or ["memcheck", "racecheck"]
        for tool in selected:
            if tool not in SANITIZER_TOOLS:
                raise BoardError(f"unknown sanitizer tool '{tool}'; choose from {SANITIZER_TOOLS}")
        board = get_board(self._board_id)
        result = CudaCheckResult()
        self._run_dir.mkdir(parents=True, exist_ok=True)
        async with open_runner(board) as runner:
            if build_command:
                await self._build(runner, build_command, timeout_s)
            for tool in selected:
                errors, count = await self._run_tool(runner, tool, run_command, timeout_s)
                result.errors.extend(errors)
                result.summaries[tool] = count
        result.persist(self._run_dir)
        return result

    async def _build(self, runner: _Runner, build_command: str, timeout_s: float) -> None:
        built = await runner.run(build_command, timeout_s=timeout_s)
        (self._run_dir / "build.txt").write_text(built.stdout + built.stderr)
        if built.exit_status != 0:
            raise BoardError(
                f"CUDA build failed (exit {built.exit_status}): {built.stderr.strip()[:400]}"
            )

    async def _run_tool(
        self, runner: _Runner, tool: str, run_command: str, timeout_s: float
    ) -> tuple[list[SanitizerError], int]:
        _logger.info("cuda_sanitizer", tool=tool)
        completed = await runner.run(sanitizer_command(tool, run_command), timeout_s=timeout_s)
        output = completed.stdout + completed.stderr
        (self._run_dir / f"{tool}.txt").write_text(output)
        return parse_sanitizer_report(tool, output)
