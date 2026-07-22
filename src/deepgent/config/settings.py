"""Settings models and loaders.

Precedence, highest first: explicit init kwargs, DEEPGENT_ environment
variables, .deepgent/config.toml (project), ~/.deepgent/config.toml (user),
versions.toml [models]. Model IDs come only from versions.toml.
"""

import tomllib
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

from deepgent.errors import ConfigError

VERSIONS_FILE = "versions.toml"
CONFIG_RELPATH = Path(".deepgent") / "config.toml"

PermissionMode = Literal["default", "acceptEdits", "plan", "bypassPermissions", "dontAsk", "auto"]


class ModelTiers(BaseModel):
    """Model IDs per routing tier (section 9). Sourced from versions.toml."""

    opus: str
    sonnet: str
    haiku: str


class BudgetSettings(BaseModel):
    """Spend limits enforced by budget_guard (section 9)."""

    per_task_usd: float = 2.00


class TierPricing(BaseModel):
    """List prices in USD per million tokens. Sourced from versions.toml."""

    input: float
    output: float
    cache_read: float
    cache_write: float


class PricingTiers(BaseModel):
    """Per-tier pricing used for in-flight budget estimation."""

    opus: TierPricing
    sonnet: TierPricing
    haiku: TierPricing


class DeepgentSettings(BaseSettings):
    """Runtime settings, overridable via DEEPGENT_ environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="DEEPGENT_", env_nested_delimiter="__", extra="ignore"
    )

    models: ModelTiers
    pricing: PricingTiers
    budget: BudgetSettings = BudgetSettings()
    default_board: str | None = None
    telemetry_enabled: bool = True
    permission_mode: PermissionMode = "default"
    max_turns: int = 50
    ci: bool = False


class _MappingSource(PydanticBaseSettingsSource):
    """Feeds a pre-merged file-config mapping into pydantic-settings."""

    def __init__(self, settings_cls: type[BaseSettings], data: dict[str, Any]) -> None:
        super().__init__(settings_cls)
        self._data = data

    def get_field_value(self, field: Any, field_name: str) -> tuple[Any, str, bool]:
        return self._data.get(field_name), field_name, False

    def __call__(self) -> dict[str, Any]:
        fields = self.settings_cls.model_fields
        return {k: v for k, v in self._data.items() if k in fields}


def find_versions_file(start: Path | None = None) -> Path:
    """Locate versions.toml by walking up from start. With no start, walk up
    from the cwd and then from the package location (repo checkouts)."""
    roots = [start] if start is not None else [Path.cwd(), Path(__file__).resolve()]
    for root in roots:
        for candidate in [root, *root.parents]:
            path = candidate / VERSIONS_FILE
            if path.is_file():
                return path
    raise ConfigError(
        f"{VERSIONS_FILE} not found from {roots[0]} upward. Run deepgent from a "
        "checkout containing it, or pass project_root to load_settings()."
    )


def _read_toml(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as f:
            return tomllib.load(f)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"invalid TOML in {path}: {exc}") from exc


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _merged_file_config(project_root: Path | None) -> dict[str, Any]:
    versions_path = find_versions_file(project_root)
    versions = _read_toml(versions_path)
    for table in ("models", "pricing"):
        if table not in versions:
            raise ConfigError(f"{versions_path} has no [{table}] table")
    data: dict[str, Any] = {
        "models": versions["models"],
        "pricing": versions["pricing"],
    }

    root = project_root if project_root is not None else versions_path.parent
    for config_path in [Path.home() / CONFIG_RELPATH, root / CONFIG_RELPATH]:
        if config_path.is_file():
            data = _deep_merge(data, _read_toml(config_path))
    return data


def load_settings(project_root: Path | None = None) -> DeepgentSettings:
    """Build settings from versions.toml, config files, and environment."""
    data = _merged_file_config(project_root)

    class _LoadedSettings(DeepgentSettings):
        @classmethod
        def settings_customise_sources(
            cls,
            settings_cls: type[BaseSettings],
            init_settings: PydanticBaseSettingsSource,
            env_settings: PydanticBaseSettingsSource,
            dotenv_settings: PydanticBaseSettingsSource,
            file_secret_settings: PydanticBaseSettingsSource,
        ) -> tuple[PydanticBaseSettingsSource, ...]:
            return (init_settings, env_settings, _MappingSource(settings_cls, data))

    # models arrives via the settings sources above, invisible to mypy.
    return _LoadedSettings()  # type: ignore[call-arg]
