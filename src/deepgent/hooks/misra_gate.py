"""misra_gate: PostToolUse hook on C/C++ writes (section 10).

Runs cppcheck's MISRA addon and a clang-tidy profile inside the jp6
toolchain container on every written or edited C/C++ file, blocks completion
on violations, and reports them as structured findings the model can fix.
Fail-closed: if the analysis cannot run, the write is blocked with the
reason, never silently waved through.

License note: cppcheck's misra addon emits rule numbers only; no MISRA rule
text ships with or is fetched by deepgent.
"""

import asyncio
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import structlog
from claude_agent_sdk.types import (
    HookContext,
    HookInput,
    PostToolUseHookInput,
    SyncHookJSONOutput,
)

from deepgent.containers import ContainerBuilder, load_jp6_spec
from deepgent.errors import ContainerError, DeepgentError

_logger = structlog.get_logger(__name__)

C_CPP_SUFFIXES = frozenset({".c", ".cc", ".cpp", ".h", ".hpp"})
_WRITE_TOOLS = frozenset({"Write", "Edit"})
_ANALYSIS_TIMEOUT_S = 180.0

# Curated clang-tidy profile: correctness-focused, no style bikeshedding.
CLANG_TIDY_CHECKS = "-*,bugprone-*,clang-analyzer-*,cert-*,concurrency-*"

# cppcheck: {file}:{line}:{severity}:{id}:{message}
_CPPCHECK_TEMPLATE = "{file}|{line}|{severity}|{id}|{message}"
_CPPCHECK_LINE = re.compile(
    r"^(?P<file>[^|]+)\|(?P<line>\d+)\|(?P<sev>[^|]+)\|(?P<id>[^|]+)\|(?P<msg>.*)$"
)
# clang-tidy: file:line:col: warning: message [check-name]
_CLANG_TIDY_LINE = re.compile(
    r"^(?P<file>[^:]+):(?P<line>\d+):\d+:\s+(?:warning|error):\s+(?P<msg>.*?)\s+\[(?P<id>[^\]]+)\]$"
)


@dataclass(frozen=True)
class Finding:
    """One static-analysis violation."""

    tool: str
    file: str
    line: int
    rule: str
    message: str

    def describe(self) -> str:
        return f"{self.file}:{self.line} [{self.tool}:{self.rule}] {self.message}"


def is_gated_file(file_path: str) -> bool:
    return Path(file_path).suffix in C_CPP_SUFFIXES


def parse_cppcheck(output: str) -> list[Finding]:
    findings = []
    for line in output.splitlines():
        match = _CPPCHECK_LINE.match(line.strip())
        # checkersReport is meta-noise, not a violation.
        if match and match.group("id") != "checkersReport":
            findings.append(
                Finding(
                    tool="cppcheck",
                    file=match.group("file"),
                    line=int(match.group("line")),
                    rule=match.group("id"),
                    message=match.group("msg").strip(),
                )
            )
    return findings


def parse_clang_tidy(output: str) -> list[Finding]:
    findings = []
    for line in output.splitlines():
        match = _CLANG_TIDY_LINE.match(line.strip())
        if match:
            findings.append(
                Finding(
                    tool="clang-tidy",
                    file=match.group("file"),
                    line=int(match.group("line")),
                    rule=match.group("id"),
                    message=match.group("msg").strip(),
                )
            )
    return findings


def analysis_command(image_tag: str, file_path: Path) -> list[str]:
    """docker command running both analyzers on one file in the container."""
    name = file_path.name
    inner = (
        f"cppcheck --addon=misra --enable=warning,style --inline-suppr "
        f"--template='{_CPPCHECK_TEMPLATE}' /src/{name} 2>&1; "
        f"clang-tidy -quiet -checks='{CLANG_TIDY_CHECKS}' /src/{name} -- "
        f"-std=c++17 2>/dev/null"
    )
    return [
        "docker",
        "run",
        "--rm",
        "--platform",
        "linux/arm64",
        "-v",
        f"{file_path.parent}:/src:ro",
        image_tag,
        "bash",
        "-c",
        inner,
    ]


async def run_analysis(file_path: Path) -> list[Finding]:
    """Run both analyzers in the toolchain container and parse findings."""
    spec = load_jp6_spec()
    builder = ContainerBuilder(spec)
    builder.preflight()
    if not builder.image_exists():
        raise ContainerError(
            f"toolchain image {spec.image_tag} is not built; run: deepgent containers build jp6"
        )
    command = analysis_command(spec.image_tag, file_path)
    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    try:
        raw, _ = await asyncio.wait_for(process.communicate(), timeout=_ANALYSIS_TIMEOUT_S)
    except TimeoutError as exc:
        process.kill()
        raise ContainerError(
            f"static analysis timed out after {_ANALYSIS_TIMEOUT_S:.0f}s on {file_path.name}"
        ) from exc
    output = raw.decode(errors="replace")
    return parse_cppcheck(output) + parse_clang_tidy(output)


def make_misra_gate() -> Any:
    """Build the misra_gate callback."""

    async def misra_gate(
        input_data: HookInput,
        tool_use_id: str | None,
        context: HookContext,
    ) -> SyncHookJSONOutput:
        data = cast(PostToolUseHookInput, input_data)
        if data["tool_name"] not in _WRITE_TOOLS:
            return {}
        raw_path = str(data["tool_input"].get("file_path", ""))
        if not raw_path or not is_gated_file(raw_path):
            return {}
        file_path = Path(raw_path)
        if not file_path.is_absolute():
            file_path = Path(data["cwd"]) / file_path
        if not file_path.is_file():
            return {}

        log = _logger.bind(file=str(file_path))
        try:
            findings = await run_analysis(file_path)
        except DeepgentError as exc:
            # Fail closed: an unrunnable gate must not wave code through.
            log.warning("misra_gate_unavailable", error=str(exc))
            return {
                "decision": "block",
                "reason": (f"misra_gate could not run static analysis on {file_path.name}: {exc}"),
            }

        if not findings:
            log.info("misra_gate_clean")
            return {}
        log.info("misra_gate_violations", count=len(findings))
        listing = "\n".join(f.describe() for f in findings[:50])
        return {
            "decision": "block",
            "reason": (
                f"static analysis found {len(findings)} violation(s) in "
                f"{file_path.name}; fix them before proceeding:\n{listing}"
            ),
        }

    return misra_gate
