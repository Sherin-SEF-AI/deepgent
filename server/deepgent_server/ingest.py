"""Ingestion: split public datasheet documents into provenance-carrying chunks.

v0 handles PDF (per-page text via pypdf, heading-aware splitting) and plain
text/markdown (heading-aware). Table-aware extraction and errata weighting
arrive later; chunk metadata is stable so re-ingestion upgrades in place.
"""

import re
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader

_MAX_CHUNK_CHARS = 2400
_HEADING = re.compile(r"^(?:#{1,6}\s+.+|\d+(?:\.\d+)*\s+[A-Z].{3,80}|[A-Z][A-Z0-9 /_-]{6,80})$")


@dataclass(frozen=True)
class RawChunk:
    """A chunk ready for the store, before hashing."""

    section: str
    text: str


def _split_sections(lines: list[str], default_section: str) -> list[RawChunk]:
    chunks: list[RawChunk] = []
    section = default_section
    buffer: list[str] = []

    def flush() -> None:
        text = "\n".join(buffer).strip()
        buffer.clear()
        if not text:
            return
        # Oversized sections split on paragraph boundaries.
        while len(text) > _MAX_CHUNK_CHARS:
            cut = text.rfind("\n\n", 0, _MAX_CHUNK_CHARS)
            if cut <= 0:
                cut = _MAX_CHUNK_CHARS
            chunks.append(RawChunk(section=section, text=text[:cut].strip()))
            text = text[cut:].strip()
        if text:
            chunks.append(RawChunk(section=section, text=text))

    for line in lines:
        stripped = line.strip()
        if stripped and _HEADING.match(stripped):
            flush()
            section = stripped.lstrip("# ").strip()
        else:
            buffer.append(line)
    flush()
    return chunks


def chunk_text(content: str, default_section: str = "body") -> list[RawChunk]:
    return _split_sections(content.splitlines(), default_section)


def chunk_pdf(path: Path) -> list[RawChunk]:
    reader = PdfReader(str(path))
    chunks: list[RawChunk] = []
    for page_number, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        if not text.strip():
            continue
        chunks.extend(_split_sections(text.splitlines(), default_section=f"page {page_number}"))
    return chunks


def chunk_file(path: Path) -> list[RawChunk]:
    if path.suffix.lower() == ".pdf":
        return chunk_pdf(path)
    return chunk_text(path.read_text())
