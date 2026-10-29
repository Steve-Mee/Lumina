"""Registered economic templates. LLM/free-form generation is refused."""

from __future__ import annotations

REGISTERED_TEMPLATE_IDS: frozenset[str] = frozenset(
    {
        "mean_reversion",
        "volume_imbalance",
        "regime_momentum",
        "opening_range_breakout",
        "opening_range_fade",
        "overnight_gap",
        "vwap_distance",
        "range_compression",
        "close_reversal",
        "time_of_day_inventory",
        "trend_pullback",
        "volatility_expansion",
    }
)


class TemplateRefused(ValueError):
    """A hypothesis is not a registered economic template."""


def require_economic_template(template_id: str) -> str:
    ident = template_id.strip()
    if ident not in REGISTERED_TEMPLATE_IDS:
        raise TemplateRefused(
            f"economic hypotheses must use a registered template, not free-form {template_id!r}"
        )
    return ident
