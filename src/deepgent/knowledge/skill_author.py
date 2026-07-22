"""Skill self-authoring: draft a skill from clustered corpus tuples (Tier 3).

When the failure corpus accumulates N tuples sharing a theme, deepgent drafts
a SKILL.md candidate from them. The human gate stays: this only writes a
candidate file (and, in CI, opens a PR); it never merges. Every drafted claim
cites the verification_run_id of the tuple it came from, so the skill stays
evidence-backed like the hand-written packs.
"""

import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import structlog

_logger = structlog.get_logger(__name__)

_MIN_CLUSTER = 3
_STOPWORDS = frozenset(
    {"the", "a", "an", "on", "in", "of", "to", "for", "with", "and", "is", "at", "fatal"}
)
_WORD = re.compile(r"[a-z0-9]+")


def _theme_key(symptom: str) -> str:
    """A coarse cluster key: the most salient non-stopword token."""
    words = [w for w in _WORD.findall(symptom.lower()) if w not in _STOPWORDS and len(w) > 2]
    return words[0] if words else "misc"


@dataclass
class SkillCandidate:
    """A drafted skill awaiting human review."""

    name: str
    theme: str
    tuples: list[dict[str, Any]] = field(default_factory=list)

    def render_skill_md(self) -> str:
        description = (
            f"Resolved {self.theme} failures on Jetson, drafted from "
            f"{len(self.tuples)} verified corpus tuples. Human review required "
            "before this skill is trusted."
        )
        lines = [
            "---",
            f"name: {self.name}",
            f"description: {description}",
            "---",
            "",
            f"# {self.theme} failures (corpus-drafted, unreviewed)",
            "",
            "Each entry is a previously resolved, verified failure. Review and "
            "prune before merging; this file was auto-drafted from the failure "
            "corpus.",
            "",
        ]
        for tup in self.tuples:
            lines += [
                f"## {tup.get('symptom', 'symptom')}",
                "",
                f"- root cause: {tup.get('root_cause', '')}",
                f"- fix: {tup.get('fix', '')}",
                f"- verified by: {tup.get('verification_run_id', '')}",
                "",
            ]
        return "\n".join(lines)


def cluster_tuples(
    tuples: list[dict[str, Any]], min_cluster: int = _MIN_CLUSTER
) -> list[SkillCandidate]:
    """Group corpus tuples into skill candidates by theme; only clusters of
    at least min_cluster become candidates."""
    by_theme: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for tup in tuples:
        by_theme[_theme_key(str(tup.get("symptom", "")))].append(tup)
    candidates = []
    for theme, group in sorted(by_theme.items()):
        if len(group) >= min_cluster:
            candidates.append(
                SkillCandidate(
                    name=f"corpus-{theme}",
                    theme=theme,
                    tuples=group,
                )
            )
    _logger.info("skill_clusters", candidates=len(candidates), tuples=len(tuples))
    return candidates


def draft_skill_candidates(
    tuples: list[dict[str, Any]],
    skills_dir: Path,
    min_cluster: int = _MIN_CLUSTER,
) -> list[Path]:
    """Write drafted SKILL.md candidates under skills_dir/<name>-draft/.

    Draft directories are suffixed so they never shadow reviewed packs, and
    the human gate (PR review) remains the only path to a trusted skill.
    """
    written = []
    for candidate in cluster_tuples(tuples, min_cluster):
        target = skills_dir / f"{candidate.name}-draft"
        target.mkdir(parents=True, exist_ok=True)
        skill_md = target / "SKILL.md"
        skill_md.write_text(candidate.render_skill_md())
        written.append(skill_md)
    return written
