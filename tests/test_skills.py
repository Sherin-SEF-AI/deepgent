"""Skill pack parsing, listing, and session sync."""

from pathlib import Path

import pytest

from deepgent.errors import ConfigError
from deepgent.knowledge import list_skills, sync_skills

_VALID_SKILL = """\
---
name: test-skill
description: A skill for testing the loader.
---

# Test skill

Body content with instructions.
"""


def _make_skill(root: Path, dirname: str, content: str = _VALID_SKILL) -> Path:
    skill_dir = root / dirname
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(content)
    return skill_dir


class TestListing:
    @pytest.mark.unit
    def test_lists_valid_packs(self, tmp_path: Path) -> None:
        _make_skill(tmp_path, "test-skill")
        packs = list_skills(tmp_path)
        assert len(packs) == 1
        assert packs[0].name == "test-skill"
        assert "testing the loader" in packs[0].description

    @pytest.mark.unit
    def test_missing_source_is_empty(self, tmp_path: Path) -> None:
        assert list_skills(tmp_path / "absent") == []

    @pytest.mark.unit
    def test_dirs_without_skill_md_ignored(self, tmp_path: Path) -> None:
        (tmp_path / "not-a-skill").mkdir()
        assert list_skills(tmp_path) == []

    @pytest.mark.unit
    def test_missing_frontmatter_rejected(self, tmp_path: Path) -> None:
        _make_skill(tmp_path, "bad", content="# no frontmatter\n")
        with pytest.raises(ConfigError, match="frontmatter"):
            list_skills(tmp_path)

    @pytest.mark.unit
    def test_incomplete_frontmatter_rejected(self, tmp_path: Path) -> None:
        _make_skill(tmp_path, "bad", content="---\nname: x\n---\nbody\n")
        with pytest.raises(ConfigError, match="name and description"):
            list_skills(tmp_path)


class TestSync:
    @pytest.mark.unit
    def test_sync_copies_into_project(self, tmp_path: Path) -> None:
        source = tmp_path / "source"
        _make_skill(source, "test-skill")
        (source / "test-skill" / "references").mkdir()
        (source / "test-skill" / "references" / "deep.md").write_text("detail")

        project = tmp_path / "project"
        project.mkdir()
        names = sync_skills(project, source)
        assert names == ["test-skill"]
        synced = project / ".claude" / "skills" / "test-skill"
        assert (synced / "SKILL.md").is_file()
        assert (synced / "references" / "deep.md").read_text() == "detail"

    @pytest.mark.unit
    def test_sync_replaces_stale_content(self, tmp_path: Path) -> None:
        source = tmp_path / "source"
        _make_skill(source, "test-skill")
        project = tmp_path / "project"
        project.mkdir()
        sync_skills(project, source)
        stale = project / ".claude" / "skills" / "test-skill" / "stale.md"
        stale.write_text("leftover")
        sync_skills(project, source)
        assert not stale.exists()

    @pytest.mark.unit
    def test_sync_with_no_source_is_noop(self, tmp_path: Path) -> None:
        project = tmp_path / "project"
        project.mkdir()
        assert sync_skills(project, tmp_path / "absent") == []
        assert not (project / ".claude").exists()


class TestRepoSkills:
    @pytest.mark.unit
    def test_repo_skill_packs_are_valid(self) -> None:
        repo_root = Path(__file__).resolve().parent.parent
        packs = list_skills(repo_root / "skills")
        names = {pack.name for pack in packs}
        assert names >= {"jetson-bringup", "tensorrt-quantization", "ros2-systems"}
        for pack in packs:
            body = (pack.path / "SKILL.md").read_text()
            assert len(body.splitlines()) <= 150, f"{pack.name} SKILL.md exceeds 150 lines"
