"""Deterministic failure classification into the taxonomy v0 tags.

Only confident matches classify; everything else stays None rather than
carrying a wrong tag into the flywheel.
"""

import re

_TAG_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "deploy_ssh",
        re.compile(
            r"(?i)ssh|sftp|host key|connection (refused|reset|timed out)"
            r"|unreachable board|cannot reach board"
        ),
    ),
    (
        "static_analysis",
        re.compile(r"(?i)clang-tidy|cppcheck|misra|ruff|mypy|static analysis"),
    ),
    (
        "unit_test",
        re.compile(r"(?i)pytest|\bfailed\b.*\btest|\btest\b.*\bfailed\b|assert(ion)? ?error"),
    ),
    (
        "build_deps",
        re.compile(
            r"(?i)no module named|unresolved import|apt-get|pip install"
            r"|uv sync|package .* not found|dependency"
        ),
    ),
    (
        "build_toolchain",
        re.compile(
            r"(?i)docker build|nvcc|compilation terminated|undefined reference"
            r"|linker|cmake error|make: \*\*\*"
        ),
    ),
    (
        "runtime_crash",
        re.compile(
            r"(?i)segmentation fault|core dumped|cuda error|illegal memory access"
            r"|traceback \(most recent call last\)|panic"
        ),
    ),
    ("thermal", re.compile(r"(?i)thermal|throttl|overtemp")),
    (
        "perf_miss",
        re.compile(r"(?i)latency .* exceed|below .* fps|perf(ormance)? (target|budget) miss"),
    ),
]


def classify_failure(tool_name: str, error: str) -> str | None:
    """Best-effort taxonomy tag for a failed tool call; None when unsure."""
    haystack = f"{tool_name}\n{error}"
    for tag, pattern in _TAG_PATTERNS:
        if pattern.search(haystack):
            return tag
    return None
