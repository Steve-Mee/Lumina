"""Birth history_loader prefer_daysback_only gating."""

from __future__ import annotations

from typing import Any

import pytest

from lumina_core.birth.history_loader import load_historical_ticks


@pytest.mark.unit
def test_load_historical_ticks_prefers_daysback_only_for_short_window() -> None:
    captured: dict[str, Any] = {}

    class _Svc:
        def load_historical_ohlc_extended(self, **kwargs: Any) -> list[dict[str, Any]]:
            captured.update(kwargs)
            return [{"timestamp": "2026-07-20T00:00:00Z", "close": 5000.0}]

    rows = load_historical_ticks(
        market_data_service=_Svc(),
        runtime=None,
        days_back=7,
        limit=None,
    )
    assert rows
    assert captured.get("prefer_daysback_only") is True


@pytest.mark.unit
def test_load_historical_ticks_paginates_for_long_birth_window() -> None:
    captured: dict[str, Any] = {}

    class _Svc:
        def load_historical_ohlc_extended(self, **kwargs: Any) -> list[dict[str, Any]]:
            captured.update(kwargs)
            return [{"timestamp": "2026-07-20T00:00:00Z", "close": 5000.0}]

    rows = load_historical_ticks(
        market_data_service=_Svc(),
        runtime=None,
        days_back=90,
        limit=None,
    )
    assert rows
    assert captured.get("prefer_daysback_only") is False
    assert captured.get("days_back") == 90
