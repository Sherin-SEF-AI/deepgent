"""Settings loading and precedence tests."""

import shutil
import tomllib
from pathlib import Path

import pytest

from deepgent.config import find_versions_file, load_settings
from deepgent.errors import ConfigError

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def _isolate_user_config(
    tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Point HOME at an empty dir so a developer's real ~/.deepgent/config.toml
    (written by `deepgent setup`) never leaks into these precedence tests.
    Tests that need a user config set HOME again, overriding this."""
    monkeypatch.setenv("HOME", str(tmp_path_factory.mktemp("empty-home")))


def _versions_models() -> dict[str, str]:
    with (REPO_ROOT / "versions.toml").open("rb") as f:
        models: dict[str, str] = tomllib.load(f)["models"]
    return models


@pytest.mark.unit
def test_models_come_from_versions_toml() -> None:
    settings = load_settings(REPO_ROOT)
    expected = _versions_models()
    assert settings.models.opus == expected["opus"]
    assert settings.models.sonnet == expected["sonnet"]
    assert settings.models.haiku == expected["haiku"]


@pytest.mark.unit
def test_defaults() -> None:
    settings = load_settings(REPO_ROOT)
    assert settings.budget.per_task_usd == 2.00
    assert settings.default_board is None
    assert settings.telemetry_enabled is True
    assert settings.permission_mode == "default"
    assert settings.max_turns == 50


@pytest.mark.unit
def test_env_overrides_files(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEEPGENT_BUDGET__PER_TASK_USD", "0.50")
    monkeypatch.setenv("DEEPGENT_DEFAULT_BOARD", "agx-orin")
    settings = load_settings(REPO_ROOT)
    assert settings.budget.per_task_usd == 0.50
    assert settings.default_board == "agx-orin"


@pytest.mark.unit
def test_project_config_overrides_user_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    shutil.copy(REPO_ROOT / "versions.toml", tmp_path / "versions.toml")

    home = tmp_path / "home"
    (home / ".deepgent").mkdir(parents=True)
    (home / ".deepgent" / "config.toml").write_text(
        'default_board = "user-board"\n[budget]\nper_task_usd = 1.00\n'
    )
    monkeypatch.setenv("HOME", str(home))

    project = tmp_path / "project"
    (project / ".deepgent").mkdir(parents=True)
    (project / ".deepgent" / "config.toml").write_text("[budget]\nper_task_usd = 0.80\n")

    settings = load_settings(project)
    assert settings.budget.per_task_usd == 0.80
    assert settings.default_board == "user-board"
    assert settings.models.opus == _versions_models()["opus"]


@pytest.mark.unit
def test_missing_versions_toml_raises(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match=r"versions\.toml not found"):
        find_versions_file(tmp_path)


@pytest.mark.unit
def test_versions_toml_without_models_raises(tmp_path: Path) -> None:
    (tmp_path / "versions.toml").write_text('[jetson.jp6]\njetpack = "6.2"\n')
    with pytest.raises(ConfigError, match=r"no \[models\] table"):
        load_settings(tmp_path)


@pytest.mark.unit
def test_versions_toml_without_pricing_raises(tmp_path: Path) -> None:
    (tmp_path / "versions.toml").write_text('[models]\nopus = "o"\nsonnet = "s"\nhaiku = "h"\n')
    with pytest.raises(ConfigError, match=r"no \[pricing\] table"):
        load_settings(tmp_path)


@pytest.mark.unit
def test_pricing_comes_from_versions_toml() -> None:
    settings = load_settings(REPO_ROOT)
    with (REPO_ROOT / "versions.toml").open("rb") as f:
        expected = tomllib.load(f)["pricing"]
    assert settings.pricing.sonnet.input == expected["sonnet"]["input"]
    assert settings.pricing.opus.output == expected["opus"]["output"]
    assert settings.pricing.haiku.cache_read == expected["haiku"]["cache_read"]
