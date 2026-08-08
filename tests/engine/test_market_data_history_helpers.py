"""Regression: history helpers must not depend on undefined _mds after M5 extract."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from lumina_core.engine.market_data_history_helpers import MarketDataHistoryHelpersMixin


@pytest.mark.unit
def test_utc_iso_z_and_day_floor_without_mds() -> None:
    """Birth history load crashed with NameError: _mds is not defined."""
    dt = datetime(2026, 6, 15, 14, 30, 0)
    iso = MarketDataHistoryHelpersMixin._utc_iso_z(dt)
    assert iso.endswith("Z")
    assert "2026-06-15" in iso

    floored = MarketDataHistoryHelpersMixin._utc_day_floor(dt)
    assert floored.hour == 0
    assert floored.tzinfo is not None


@pytest.mark.unit
def test_sanitize_historical_payload_dates_iso() -> None:
    out = MarketDataHistoryHelpersMixin._sanitize_historical_payload_dates(
        {"from": "2026-01-01", "to": "2026-01-02T00:00:00Z"}
    )
    assert out["from"].endswith("Z")
    assert out["to"] == "2026-01-02T00:00:00Z"


@pytest.mark.unit
def test_sort_and_cap_bars() -> None:
    bars = [
        {"epoch": 2, "last": 2.0},
        {"epoch": 1, "last": 1.0},
        {"timestamp": datetime(2026, 1, 1, tzinfo=timezone.utc).isoformat(), "last": 3.0},
    ]
    sorted_bars = MarketDataHistoryHelpersMixin._sort_and_cap_bars(bars, target_cap=2)
    assert len(sorted_bars) == 2
    assert sorted_bars[0]["epoch"] == 1
