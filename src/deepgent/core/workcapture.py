"""Workspace capture for the GUI code cockpit.

Deterministic, Qt-free helpers that read the real workspace after (or during)
a task: the git diff of what changed, the list of changed files, and running a
review or test command and capturing its result. The agent does the editing;
these surface the evidence (diff, review findings, test pass/fail) so the GUI
can show a code -> review -> test loop.
"""

import subprocess
from dataclasses import dataclass
from pathlib import Path

_TIMEOUT_S = 600


@dataclass(frozen=True)
class CommandRun:
    """The outcome of a review or test command."""

    command: str
    exit_status: int
    output: str

    @property
    def ok(self) -> bool:
        return self.exit_status == 0


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(cwd), "--no-pager", *args],
        capture_output=True,
        text=True,
        timeout=60,
    )


def is_git_repo(cwd: Path) -> bool:
    try:
        result = _git(cwd, "rev-parse", "--is-inside-work-tree")
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0 and result.stdout.strip() == "true"


def changed_files(cwd: Path) -> list[tuple[str, str]]:
    """(status, path) for every changed/untracked file, via git status."""
    if not is_git_repo(cwd):
        return []
    result = _git(cwd, "status", "--porcelain")
    files: list[tuple[str, str]] = []
    for line in result.stdout.splitlines():
        if len(line) > 3:
            files.append((line[:2].strip() or "?", line[3:].strip()))
    return files


def git_diff(cwd: Path) -> str:
    """Unstaged + staged diff of tracked files, plus a list of untracked ones.

    Non-mutating: it never touches the index. Untracked (newly created) files
    are listed by name since they have no diff base.
    """
    if not is_git_repo(cwd):
        return "(not a git repository; diff unavailable)"
    tracked = _git(cwd, "diff", "HEAD").stdout
    untracked = [path for status, path in changed_files(cwd) if status == "??"]
    parts: list[str] = []
    if tracked.strip():
        parts.append(tracked.rstrip())
    if untracked:
        parts.append("# untracked (new) files:\n" + "\n".join(f"+ {p}" for p in untracked))
    return "\n\n".join(parts) if parts else "(no changes)"


def run_check(cwd: Path, command: str) -> CommandRun:
    """Run a review or test command in cwd and capture its combined output."""
    try:
        completed = subprocess.run(
            command,
            shell=True,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired:
        return CommandRun(command=command, exit_status=124, output="(command timed out)")
    except OSError as exc:
        return CommandRun(command=command, exit_status=127, output=f"(could not run: {exc})")
    output = (completed.stdout + completed.stderr).strip()
    return CommandRun(command=command, exit_status=completed.returncode, output=output)


def default_review_command(cwd: Path) -> str:
    """A sensible default review command for the project in cwd."""
    if (cwd / "pyproject.toml").is_file():
        return "ruff check ."
    return "git diff --check"


def default_test_command(cwd: Path) -> str:
    """A sensible default test command for the project in cwd."""
    if (cwd / "pyproject.toml").is_file():
        return "pytest -q"
    if (cwd / "package.json").is_file():
        return "npm test"
    return "true"
