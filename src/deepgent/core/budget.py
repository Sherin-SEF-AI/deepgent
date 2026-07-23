"""Per-task budget accounting (section 9).

Spend is estimated from streamed token usage and the versions.toml [pricing]
table; the billed figure always comes from the API result message. The
estimate exists so budget_guard can halt a task before the cap is blown.

The raw token estimate ignores the prompt-cache discount the API actually
bills, so it runs hot on cache-heavy agentic loops. To halt on real spend
rather than the hot estimate, the tracker carries a calibration factor -
the median billed/estimate ratio learned from completed tasks (the data
flywheel) - and applies it to the halt decision. With no history the factor
is 1.0, so an uncalibrated harness errs toward halting early, never toward
overspending.
"""

from collections.abc import Mapping
from typing import Any

import structlog

from deepgent.config import DeepgentSettings, TierPricing

_logger = structlog.get_logger(__name__)

# Section 9: budget_guard halts and reports at 90% of the per-task cap.
HALT_FRACTION = 0.9

# Calibration is clamped to this range so a single pathological task cannot
# drive the halt threshold to a dangerous extreme in either direction.
CALIBRATION_MIN = 0.25
CALIBRATION_MAX = 4.0

_MTOK = 1_000_000


class BudgetTracker:
    """Accumulates estimated USD spend for one task.

    spent_usd is the raw token-priced estimate (persisted as est_usd for
    calibration). calibration scales it to the learned billed/estimate ratio;
    the halt decision uses that calibrated figure.
    """

    def __init__(self, settings: DeepgentSettings, calibration: float = 1.0) -> None:
        self._settings = settings
        self.cap_usd = settings.budget.per_task_usd
        self.calibration = _clamp_calibration(calibration)
        self.spent_usd = 0.0
        self.total_tokens = 0
        self.model_mix: dict[str, int] = {}

    def _pricing_for(self, model: str) -> TierPricing:
        tiers = self._settings.models
        pricing = self._settings.pricing
        if model == tiers.opus:
            return pricing.opus
        if model == tiers.sonnet:
            return pricing.sonnet
        if model == tiers.haiku:
            return pricing.haiku
        # Unknown model: assume the most expensive tier so the estimate
        # errs toward halting early rather than overspending.
        _logger.warning("unknown_model_priced_as_opus", model=model)
        return pricing.opus

    def record_usage(self, model: str, usage: Mapping[str, Any] | None) -> None:
        """Add one assistant message's token usage to the running estimate."""
        if not usage:
            return
        tokens = int(usage.get("input_tokens", 0)) + int(usage.get("output_tokens", 0))
        self.total_tokens += tokens
        self.model_mix[model] = self.model_mix.get(model, 0) + tokens
        price = self._pricing_for(model)
        self.spent_usd += (
            float(usage.get("input_tokens", 0)) * price.input
            + float(usage.get("output_tokens", 0)) * price.output
            + float(usage.get("cache_read_input_tokens", 0)) * price.cache_read
            + float(usage.get("cache_creation_input_tokens", 0)) * price.cache_write
        ) / _MTOK

    @property
    def effective_spent_usd(self) -> float:
        """Calibrated spend estimate the halt decision acts on."""
        return self.spent_usd * self.calibration

    @property
    def halt_needed(self) -> bool:
        """True once calibrated spend reaches HALT_FRACTION of the cap."""
        return self.effective_spent_usd >= HALT_FRACTION * self.cap_usd


def _clamp_calibration(factor: float) -> float:
    """Keep a learned calibration factor inside a safe band."""
    if factor <= 0.0:
        return 1.0
    return max(CALIBRATION_MIN, min(CALIBRATION_MAX, factor))
