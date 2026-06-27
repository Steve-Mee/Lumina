from __future__ import annotations

import pytest

from lumina_core.birth.tick_enricher import enrich_ticks_for_sim


def _rising_ticks(n: int) -> list[dict]:
    return [{"last": 5000.0 + i * 2.0, "volume": 100, "source": "real"} for i in range(n)]


_TREND_KEYS = (
    "trend_regime_strength",
    "trend_adx_7",
    "trend_adx_14",
    "trend_adx_21",
    "trend_slope_5",
    "trend_slope_15",
    "trend_slope_30",
    "trend_slope_60",
    "trend_direction",
    "trend_duration_norm",
    "trend_atr_norm",
    "trend_atr_ratio",
)


@pytest.mark.unit
def test_enrich_ticks_writes_all_trend_keys_after_warmup() -> None:
    ticks = enrich_ticks_for_sim(_rising_ticks(100))
    row = ticks[80]
    for key in _TREND_KEYS:
        assert key in row


@pytest.mark.unit
def test_enrich_ticks_rising_series_positive_slopes_and_trend_up() -> None:
    ticks = enrich_ticks_for_sim(_rising_ticks(100))
    row = ticks[80]
    assert row["trend_slope_15"] > 0
    assert row["trend_slope_60"] > 0
    assert row["regime"] == "TREND_UP"
    assert row["trend_regime_strength"] > 0


@pytest.mark.unit
def test_enrich_ticks_warmup_zeros() -> None:
    ticks = enrich_ticks_for_sim(_rising_ticks(100))
    row = ticks[30]
    assert row["trend_regime_strength"] == 0.0
    assert row["regime"] == "NEUTRAL"
