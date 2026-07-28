"""Skill/golden contract gate (Part A3, WO-16)."""

from pathlib import Path

import pytest

from deepgent.knowledge.skill_gate import (
    SkillIssue,
    blocking,
    validate_skill,
    validate_skills,
)
from deepgent.knowledge.skills import SkillPack

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parent.parent


def _pack(name: str, status: str, golden: str | None = None) -> SkillPack:
    return SkillPack(name=name, description="d", path=Path("/x"), status=status, golden=golden)


def test_repo_skills_have_no_blocking_findings() -> None:
    # The gate is live but non-retroactive: nothing in the repo claims 'done'
    # yet, and no skill points at a missing golden, so CI stays green.
    issues = validate_skills(REPO_ROOT / "skills", REPO_ROOT / "golden")
    assert blocking(issues) == [], [i.message for i in blocking(issues)]


def test_done_without_golden_is_blocked() -> None:
    issues = validate_skill(_pack("s", "done"), golden_ids=set())
    assert any(i.severity == "block" and "no paired golden" in i.message for i in issues)


def test_done_with_existing_golden_passes() -> None:
    issues = validate_skill(_pack("s", "done", golden="gt-0002"), golden_ids={"gt-0002"})
    assert blocking(issues) == []


def test_declared_golden_must_exist() -> None:
    issues = validate_skill(_pack("s", "fact-verified", golden="gt-9999"), golden_ids={"gt-0002"})
    assert any(i.severity == "block" and "no such golden" in i.message for i in issues)


def test_wip_status_warns_not_blocks() -> None:
    issues = validate_skill(_pack("s", "draft"), golden_ids=set())
    assert blocking(issues) == []
    assert any(i.severity == "warn" for i in issues)


def test_issue_is_hashable_frozen() -> None:
    issue = SkillIssue("s", "block", "m")
    assert issue.skill == "s" and issue.severity == "block"
