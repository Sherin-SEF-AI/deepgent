"""Skill/golden linkage gate (expansion spec A3, WO-16).

The Part A3 contract is "no golden, no merge": a skill only earns its place in
the agent's context when a paired golden proves it. This module enforces the
linkage. It is deliberately non-retroactive: a skill still being drafted or
completed (status draft / methodology-complete / fact-verified) is not yet
claiming to meet the contract, so it is reported but not blocked. A skill that
claims status "done" MUST name a paired golden that exists, and any declared
golden must resolve. Those are blocking.

The blocking set is what CI enforces (tests/test_skill_gate.py). Running the
golden itself is the hardware/eval workflow's job; this gate enforces the
linkage so a "done" skill can never merge without one.
"""

from dataclasses import dataclass
from pathlib import Path

from deepgent.knowledge.skills import SkillPack, default_skills_dir, list_skills

# Statuses that assert the skill meets the full Part A3 contract. Any other
# status is treated as work-in-progress: exempt from the golden requirement,
# but warned so the remaining work is visible.
DONE_STATUSES = frozenset({"done", "golden-gated"})


@dataclass(frozen=True)
class SkillIssue:
    """One contract finding for a skill."""

    skill: str
    severity: str  # "block" | "warn"
    message: str


def _golden_ids(golden_dir: Path) -> set[str]:
    return {p.stem for p in golden_dir.glob("*.yaml")}


def validate_skill(pack: SkillPack, golden_ids: set[str]) -> list[SkillIssue]:
    """Contract findings for a single skill."""
    issues: list[SkillIssue] = []
    if pack.golden and pack.golden not in golden_ids:
        issues.append(
            SkillIssue(
                pack.name,
                "block",
                f"declares paired golden '{pack.golden}' but no such golden exists",
            )
        )
    if pack.status in DONE_STATUSES:
        if not pack.golden:
            issues.append(
                SkillIssue(
                    pack.name,
                    "block",
                    "status is 'done' but no paired golden is declared "
                    "(Part A3: no golden, no merge)",
                )
            )
    else:
        issues.append(
            SkillIssue(
                pack.name,
                "warn",
                f"status '{pack.status}': not yet contract-complete "
                "(needs a paired golden and review)",
            )
        )
    return issues


def validate_skills(
    skills_dir: Path | None = None, golden_dir: Path | None = None
) -> list[SkillIssue]:
    """Findings across all skills. Blocking findings fail the CI gate."""
    source = skills_dir if skills_dir is not None else default_skills_dir()
    if golden_dir is None:
        base = source.parent if source is not None else Path.cwd()
        golden_dir = base / "golden"
    golden_ids = _golden_ids(golden_dir) if golden_dir.is_dir() else set()
    issues: list[SkillIssue] = []
    for pack in list_skills(source):
        issues.extend(validate_skill(pack, golden_ids))
    return issues


def blocking(issues: list[SkillIssue]) -> list[SkillIssue]:
    """Only the findings that must fail a merge."""
    return [i for i in issues if i.severity == "block"]


def render_report(issues: list[SkillIssue]) -> str:
    """Human-readable gate report."""
    if not issues:
        return "skill gate: no findings"
    blocks = blocking(issues)
    lines = [f"skill gate: {len(blocks)} blocking, {len(issues) - len(blocks)} warnings", ""]
    for issue in sorted(issues, key=lambda i: (i.severity != "block", i.skill)):
        mark = "BLOCK" if issue.severity == "block" else "warn "
        lines.append(f"  [{mark}] {issue.skill}: {issue.message}")
    return "\n".join(lines)
