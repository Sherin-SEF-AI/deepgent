"""Per-task budget accounting (section 9).

Spend is estimated from streamed token usage and the versions.toml [pricing]
table; the billed figure always comes from the API result message. The
estimate exists so budget_guard can halt a task before the cap is blown.
"""

from collections.abc import Mapping
from typing import Any

import structlog

from deepgent.config import DeepgentSettings, TierPricing

_logger = structlog.get_logger(__name__)

# Section 9: budget_guard halts and reports at 90% of the per-task cap.
HALT_FRACTION = 0.9

_MTOK = 1_000_000


class BudgetTracker:
    """Accumulates estimated USD spend for one task."""

    def __init__(self, settings: DeepgentSettings) -> None:
        self._settings = settings
        self.cap_usd = settings.budget.per_task_usd
        self.spent_usd = 0.0

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
        price = self._pricing_for(model)
        self.spent_usd += (
            float(usage.get("input_tokens", 0)) * price.input
            + float(usage.get("output_tokens", 0)) * price.output
            + float(usage.get("cache_read_input_tokens", 0)) * price.cache_read
            + float(usage.get("cache_creation_input_tokens", 0)) * price.cache_write
        ) / _MTOK

    @property
    def halt_needed(self) -> bool:
        """True once estimated spend reaches HALT_FRACTION of the cap."""
        return self.spent_usd >= HALT_FRACTION * self.cap_usd
