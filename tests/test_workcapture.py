"""Workspace capture for the GUI cockpit: diff, changed files, review/test run."""

import subprocess
from pathlib import Path

import pytest

from deepgent.core.workcapture import (
    changed_files,
    default_review_command,
    default_test_command,
    git_diff,
    is_git_repo,
    run_check,
)

pytestmark = pytest.mark.unit


def _init_repo(root: Path) -> None:
    subprocess.run(["git", "-C", str(root), "init", "-q"], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.email", "t@t"], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.name", "t"], check=True)
    (root / "a.py").write_text("x = 1\n")
    subprocess.run(["git", "-C", str(root), "add", "-A"], check=True)
    subprocess.run(
        ["git", "-C", str(root), "commit", "-q", "-m", "init"],
        check=True,
        env={
            "GIT_AUTHOR_NAME": "t",
            "GIT_AUTHOR_EMAIL": "t@t",
            "GIT_COMMITTER_NAME": "t",
            "GIT_COMMITTER_EMAIL": "t@t",
            "PATH": _path(),
        },
    )


def _path() -> str:
    import os

    return os.environ.get("PATH", "/usr/bin:/bin")


def test_not_a_git_repo(tmp_path: Path) -> None:
    assert is_git_repo(tmp_path) is False
    assert changed_files(tmp_path) == []
    assert "not a git repository" in git_diff(tmp_path)


def test_diff_shows_edits_and_untracked(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    (tmp_path / "a.py").write_text("x = 2\n")  # edit tracked file
    (tmp_path / "b.py").write_text("new = True\n")  # new untracked file
    diff = git_diff(tmp_path)
    assert "-x = 1" in diff and "+x = 2" in diff
    assert "b.py" in diff  # untracked listed
    statuses = dict((path, status) for status, path in changed_files(tmp_path))
    assert statuses["b.py"] == "??"


def test_run_check_captures_output_and_exit() -> None:
    ok = run_check(Path("."), "printf hello")
    assert ok.ok and "hello" in ok.output
    bad = run_check(Path("."), "sh -c 'echo boom >&2; exit 3'")
    assert not bad.ok and bad.exit_status == 3 and "boom" in bad.output


def test_default_commands(tmp_path: Path) -> None:
    # Empty dir -> generic defaults.
    assert default_review_command(tmp_path) == "git diff --check"
    assert default_test_command(tmp_path) == "true"
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n")
    assert default_review_command(tmp_path) == "ruff check ."
    assert default_test_command(tmp_path) == "pytest -q"
