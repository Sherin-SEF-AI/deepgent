"""Seed the compatibility matrix from the repo's verified versions manifest.

`versions.toml` is deepgent's single source of truth for external stack
versions and is labelled verified in CLAUDE.md section 13. Seeding the matrix
from it gives the knowledge layer a real, provenance-carried baseline (every
claim cites the manifest, never model memory) so matrix / upgrade-check /
premortem answer with evidence instead of "unknown" on a fresh server.

Usage (owner/server side):

    python -m deepgent_server.seed --versions versions.toml --db knowledge.db
"""

import argparse
import tomllib
from pathlib import Path
from typing import Any

from deepgent_server.knowledge import KnowledgeStore

# JetPack production lines whose component pairings ship as one verified stack.
_JETSON_LINES = ("jp6", "jp7")


# The platform anchor: every other component is claimed compatible against the
# L4T version it ships with, so a query naming (l4t, <component>) resolves.
_ANCHOR = "l4t"


def _line_stack(line: dict[str, Any]) -> dict[str, str]:
    """The component -> version map for one jetson.<line> table, as strings."""
    return {component: str(version) for component, version in line.items()}


def seed_from_versions(store: KnowledgeStore, versions_path: Path) -> list[str]:
    """Seed anchored pairwise compatibility claims from versions.toml.

    Each JetPack line ships its components as one verified stack; we record one
    verified_pass claim per component paired with that line's L4T version (the
    platform anchor). A claim names only two keys, so any query carrying that
    L4T plus the component resolves to it. Returns the ids written.
    """
    manifest = tomllib.loads(versions_path.read_text())
    jetson = manifest.get("jetson", {})
    written: list[str] = []
    for line_name in _JETSON_LINES:
        line = jetson.get(line_name)
        if not line or _ANCHOR not in line:
            continue
        stack = _line_stack(line)
        anchor_version = stack[_ANCHOR]
        for component, version in sorted(stack.items()):
            if component == _ANCHOR:
                continue
            claim = store.add_claim(
                stack={_ANCHOR: anchor_version, component: version},
                claim=f"{component} {version} is the verified pairing for L4T {anchor_version}",
                status="verified_pass",
                evidence_run_id=f"versions.toml:jetson.{line_name}",
            )
            written.append(claim.id)
    return written


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the matrix from versions.toml.")
    parser.add_argument("--versions", type=Path, required=True, help="Path to versions.toml.")
    parser.add_argument("--db", type=Path, required=True, help="Knowledge sqlite db to seed.")
    args = parser.parse_args()

    store = KnowledgeStore(args.db)
    ids = seed_from_versions(store, args.versions)
    print(f"seeded {len(ids)} verified matrix claim(s) into {args.db}")


if __name__ == "__main__":
    main()
