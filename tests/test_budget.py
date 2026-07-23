"""BudgetTracker cost estimation against the versions.toml [pricing] table."""

import tomllib
from pathlib import Path

import pytest

from deepgent.config import DeepgentSettings, load_settings
from deepgent.core.budget import HALT_FRACTION, BudgetTracker

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def settings() -> DeepgentSettings:
    return load_settings(REPO_ROOT)


def _pricing(tier: str) -> dict[str, float]:
    with (REPO_ROOT / "versions.toml").open("rb") as f:
        table: dict[str, float] = tomllib.load(f)["pricing"][tier]
    return table


@pytest.mark.unit
def test_cost_math_matches_pricing_table(settings: DeepgentSettings) -> None:
    tracker = BudgetTracker(settings)
    usage = {
        "input_tokens": 200_000,
        "output_tokens": 50_000,
        "cache_read_input_tokens": 1_000_000,
        "cache_creation_input_tokens": 100_000,
    }
    tracker.record_usage(settings.models.sonnet, usage)
    p = _pricing("sonnet")
    expected = (
        0.2 * p["input"] + 0.05 * p["output"] + 1.0 * p["cache_read"] + 0.1 * p["cache_write"]
    )
    assert tracker.spent_usd == pytest.approx(expected)


@pytest.mark.unit
def test_usage_accumulates_across_tiers(settings: DeepgentSettings) -> None:
    tracker = BudgetTracker(settings)
    usage = {"output_tokens": 1_000_000}
    tracker.record_usage(settings.models.haiku, usage)
    tracker.record_usage(settings.models.opus, usage)
    expected = _pricing("haiku")["output"] + _pricing("opus")["output"]
    assert tracker.spent_usd == pytest.approx(expected)


@pytest.mark.unit
def test_unknown_model_priced_as_opus(settings: DeepgentSettings) -> None:
    tracker = BudgetTracker(settings)
    tracker.record_usage("some-future-model", {"output_tokens": 1_000_000})
    assert tracker.spent_usd == pytest.approx(_pricing("opus")["output"])


@pytest.mark.unit
def test_empty_usage_is_free(settings: DeepgentSettings) -> None:
    tracker = BudgetTracker(settings)
    tracker.record_usage(settings.models.sonnet, None)
    tracker.record_usage(settings.models.sonnet, {})
    assert tracker.spent_usd == 0.0


@pytest.mark.unit
def test_halt_threshold(settings: DeepgentSettings) -> None:
    tracker = BudgetTracker(settings)
    assert not tracker.halt_needed
    tracker.spent_usd = HALT_FRACTION * tracker.cap_usd - 0.01
    assert not tracker.halt_needed
    tracker.spent_usd = HALT_FRACTION * tracker.cap_usd
    assert tracker.halt_needed


@pytest.mark.unit
def test_cap_comes_from_budget_settings(settings: DeepgentSettings) -> None:
    custom = settings.model_copy(deep=True)
    custom.budget.per_task_usd = 0.10
    tracker = BudgetTracker(custom)
    assert tracker.cap_usd == 0.10


@pytest.mark.unit
def test_calibration_scales_halt_decision(settings: DeepgentSettings) -> None:
    # A cool calibration (billed < estimate) lets a hot estimate run further.
    tracker = BudgetTracker(settings, calibration=0.5)
    tracker.spent_usd = HALT_FRACTION * tracker.cap_usd  # would halt at 1.0
    assert not tracker.halt_needed
    assert tracker.effective_spent_usd == pytest.approx(0.5 * tracker.spent_usd)
    tracker.spent_usd = 2 * HALT_FRACTION * tracker.cap_usd
    assert tracker.halt_needed


@pytest.mark.unit
def test_calibration_is_clamped(settings: DeepgentSettings) -> None:
    # Pathological factors are pulled into the safe band; non-positive -> 1.0.
    assert BudgetTracker(settings, calibration=100.0).calibration == pytest.approx(4.0)
    assert BudgetTracker(settings, calibration=0.001).calibration == pytest.approx(0.25)
    assert BudgetTracker(settings, calibration=0.0).calibration == pytest.approx(1.0)
    assert BudgetTracker(settings, calibration=-3.0).calibration == pytest.approx(1.0)
