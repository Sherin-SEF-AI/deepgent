"""Errata watchdog: match chip errata against codebase patterns (Tier 2).

An errata entry names a chip and one or more code patterns that indicate
exposure (a register write, a device-tree binding, a driver call). The
watchdog scans the repo for those patterns and reports hits so an advisory
can be opened. Errata definitions live in the knowledge layer; the matching
is deterministic regex over tracked files.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

import structlog

_logger = structlog.get_logger(__name__)

_DEFAULT_GLOBS = ("*.c", "*.cc", "*.cpp", "*.h", "*.hpp", "*.dts", "*.dtsi", "*.py")


@dataclass(frozen=True)
class Erratum:
    """One chip erratum with exposure patterns."""

    id: str
    chip: str
    title: str
    patterns: tuple[str, ...]
    advisory: str


@dataclass(frozen=True)
class ErrataHit:
    """One matched location."""

    erratum_id: str
    chip: str
    file: str
    line: int
    text: str
    advisory: str

    def describe(self) -> str:
        return f"{self.file}:{self.line} [{self.erratum_id} / {self.chip}] {self.advisory}"


@dataclass
class ErrataScanResult:
    """All hits for a scan over a BOM's chips."""

    hits: list[ErrataHit] = field(default_factory=list)

    @property
    def exposed(self) -> bool:
        return len(self.hits) > 0

    def render_advisory(self) -> str:
        if not self.hits:
            return "# errata scan: no exposure found\n"
        lines = ["# errata advisory", "", f"{len(self.hits)} exposed location(s):", ""]
        for hit in self.hits:
            lines.append(hit.describe())
            lines.append(f"    > {hit.text.strip()[:120]}")
        return "\n".join(lines) + "\n"


def scan_errata(
    root: Path,
    errata: list[Erratum],
    bom_chips: set[str],
    globs: tuple[str, ...] = _DEFAULT_GLOBS,
) -> ErrataScanResult:
    """Scan tracked source files for patterns from errata affecting BOM chips."""
    relevant = [e for e in errata if e.chip in bom_chips]
    if not relevant:
        return ErrataScanResult()
    compiled = [
        (erratum, re.compile(pattern)) for erratum in relevant for pattern in erratum.patterns
    ]
    result = ErrataScanResult()
    files: list[Path] = []
    for glob in globs:
        files.extend(root.rglob(glob))
    for path in sorted(set(files)):
        if not path.is_file() or _is_ignored(path, root):
            continue
        try:
            lines = path.read_text(errors="replace").splitlines()
        except OSError:
            continue
        for lineno, text in enumerate(lines, start=1):
            for erratum, pattern in compiled:
                if pattern.search(text):
                    result.hits.append(
                        ErrataHit(
                            erratum_id=erratum.id,
                            chip=erratum.chip,
                            file=str(path.relative_to(root)),
                            line=lineno,
                            text=text,
                            advisory=erratum.advisory,
                        )
                    )
    _logger.info("errata_scan", chips=sorted(bom_chips), hits=len(result.hits))
    return result


def _is_ignored(path: Path, root: Path) -> bool:
    parts = set(path.relative_to(root).parts)
    return bool(parts & {".git", ".venv", "node_modules", "dist", "__pycache__"})
