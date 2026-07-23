"""CLI behavior via typer's test runner."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

import deepgent
from deepgent.cli import app

REPO_ROOT = Path(__file__).resolve().parent.parent
runner = CliRunner()


@pytest.mark.unit
def test_version_flag() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert deepgent.__version__ in result.output


@pytest.mark.unit
def test_no_task_shows_help() -> None:
    result = runner.invoke(app, [])
    assert result.exit_code == 0
    assert "Usage" in result.output


@pytest.mark.unit
def test_init_creates_project_state(tmp_path: Path) -> None:
    result = runner.invoke(app, ["init", str(tmp_path)])
    assert result.exit_code == 0
    assert (tmp_path / ".deepgent" / "project.md").is_file()
    assert (tmp_path / ".deepgent" / "config.toml").is_file()


@pytest.mark.unit
def test_init_keeps_existing_files(tmp_path: Path) -> None:
    marker = "operator-edited state"
    runner.invoke(app, ["init", str(tmp_path)])
    (tmp_path / ".deepgent" / "project.md").write_text(marker)
    result = runner.invoke(app, ["init", str(tmp_path)])
    assert result.exit_code == 0
    assert (tmp_path / ".deepgent" / "project.md").read_text() == marker


@pytest.mark.unit
def test_bare_task_dispatches_to_orchestrator(monkeypatch: pytest.MonkeyPatch) -> None:
    import deepgent.cli.main as cli_main
    from deepgent.core import TaskOutcome

    captured = {}

    class FakeOrchestrator:
        def __init__(self, settings: object, cwd: Path) -> None:
            captured["cwd"] = cwd

        async def run_task(self, task: str) -> TaskOutcome:
            captured["task"] = task
            return TaskOutcome(
                result="fake result",
                is_error=False,
                num_turns=1,
                total_cost_usd=0.01,
                session_id="s",
            )

    monkeypatch.chdir(REPO_ROOT)
    monkeypatch.setattr(cli_main, "Orchestrator", FakeOrchestrator)
    result = runner.invoke(app, ["profile the detector pipeline"])
    assert result.exit_code == 0, result.output
    assert captured["task"] == "profile the detector pipeline"
    assert "fake result" in result.output


def _hermetic_host(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin host-dependent doctor checks (uv/docker/binfmt) to healthy values
    so these tests do not depend on the CI machine's state."""
    import deepgent.host.diagnostics as diagnostics

    monkeypatch.setattr(diagnostics.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(diagnostics.platform, "machine", lambda: "aarch64")


@pytest.mark.unit
def test_ci_mode_emits_json_and_enables_ci_settings(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import json

    import deepgent.cli.main as cli_main
    from deepgent.core import TaskOutcome

    captured = {}

    class FakeOrchestrator:
        def __init__(self, settings: object, cwd: Path) -> None:
            captured["settings"] = settings

        async def run_task(self, task: str) -> TaskOutcome:
            return TaskOutcome(
                result="done",
                is_error=False,
                num_turns=2,
                total_cost_usd=0.05,
                session_id="sess-ci",
            )

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(REPO_ROOT)
    monkeypatch.setattr(cli_main, "Orchestrator", FakeOrchestrator)
    result = runner.invoke(app, ["ci", "--task", "build it", "--budget", "0.75"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output.strip().splitlines()[-1])
    assert payload["ok"] is True
    assert payload["session_id"] == "sess-ci"
    settings = captured["settings"]
    assert settings.ci is True  # type: ignore[attr-defined]
    assert settings.budget.per_task_usd == 0.75  # type: ignore[attr-defined]


@pytest.mark.unit
def test_doctor_passes_with_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(REPO_ROOT)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    _hermetic_host(monkeypatch)
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0, result.output
    assert "all checks passed" in result.output


@pytest.mark.unit
def test_doctor_fails_without_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(REPO_ROOT)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    _hermetic_host(monkeypatch)
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 1
    assert "ANTHROPIC_API_KEY is not set" in result.output
