"""Local skill pack resolution and session sync (sections 2, 11, 19).

Skill content never ships inside the client package (section 23). Phase 1
resolves packs from a local skills directory (the deepgent checkout's
skills/ dir for the owner); the authenticated fetch-and-cache client
replaces that source in later phases. At context assembly the resolved
packs are synced into the session project's .claude/skills/ directory,
which is where the Claude Code harness discovers project skills.
"""

import re
import shutil
from dataclasses import dataclass
from pathlib import Path

import structlog
import yaml

from deepgent.errors import ConfigError

_logger = structlog.get_logger(__name__)

SKILL_FILE = "SKILL.md"
SESSION_SKILLS_RELPATH = Path(".claude") / "skills"

_FRONTMATTER = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)


@dataclass(frozen=True)
class SkillPack:
    """One local skill pack and its Part A3 contract metadata."""

    name: str
    description: str
    path: Path
    # Contract metadata (expansion spec A3), all optional in frontmatter:
    status: str = "unknown"  # draft|methodology-complete|fact-verified|done|...
    tier: str | None = None  # T0..T3
    applies_to: str | None = None  # version/hardware applicability
    golden: str | None = None  # paired golden id (required once status is done)


def default_skills_dir() -> Path | None:
    """The checkout's skills/ dir, when running from a checkout."""
    for candidate in Path(__file__).resolve().parents:
        skills_dir = candidate / "skills"
        if (candidate / "versions.toml").is_file() and skills_dir.is_dir():
            return skills_dir
    return None


def _parse_skill(skill_md: Path) -> SkillPack:
    text = skill_md.read_text()
    match = _FRONTMATTER.match(text)
    if match is None:
        raise ConfigError(f"{skill_md} has no YAML frontmatter (name, description)")
    try:
        meta = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError as exc:
        raise ConfigError(f"invalid frontmatter in {skill_md}: {exc}") from exc
    name = meta.get("name")
    description = meta.get("description")
    if not name or not description:
        raise ConfigError(f"{skill_md} frontmatter must set both name and description")
    golden = meta.get("golden")
    tier = meta.get("tier")
    applies_to = meta.get("applies_to")
    return SkillPack(
        name=str(name),
        description=str(description),
        path=skill_md.parent,
        status=str(meta.get("status", "unknown")),
        tier=str(tier) if tier else None,
        applies_to=str(applies_to) if applies_to else None,
        golden=str(golden) if golden else None,
    )


def list_skills(skills_dir: Path | None = None) -> list[SkillPack]:
    """List valid skill packs in the local skills source."""
    source = skills_dir if skills_dir is not None else default_skills_dir()
    if source is None or not source.is_dir():
        return []
    packs = []
    for entry in sorted(source.iterdir()):
        skill_md = entry / SKILL_FILE
        if entry.is_dir() and skill_md.is_file():
            packs.append(_parse_skill(skill_md))
    return packs


def sync_skills(cwd: Path, skills_dir: Path | None = None) -> list[str]:
    """Copy resolved skill packs into <cwd>/.claude/skills/ and return names.

    Idempotent: each pack directory is replaced wholesale so stale files
    never linger. Projects that manage their own copy of a same-named skill
    are left untouched only if the content is identical by rewrite.
    """
    packs = list_skills(skills_dir)
    if not packs:
        return []
    target_root = cwd / SESSION_SKILLS_RELPATH
    target_root.mkdir(parents=True, exist_ok=True)
    names = []
    for pack in packs:
        target = target_root / pack.path.name
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(pack.path, target)
        names.append(pack.name)
    _logger.debug("skills_synced", cwd=str(cwd), skills=names)
    return names
