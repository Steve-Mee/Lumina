from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class MarketDataPort(Protocol):
    """Contract for ingesting and hydrating market data."""

    def load_historical_ohlc(self, days_back: int = 3, limit: int = 5000) -> bool: ...
