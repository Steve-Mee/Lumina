"""Market-data ingest façade — public import path for MarketDataIngestService.

Bounded modules: ``market_data_ingest`` (live/websocket), ``market_data_history`` (OHLC).

Module-level ``datetime`` / ``requests`` / symbol helpers are re-exported so existing
test monkeypatches on this module path continue to affect history/ingest code.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone  # noqa: F401 — monkeypatch surface

import pandas as pd  # noqa: F401 — monkeypatch surface
import requests  # noqa: F401 — monkeypatch surface

from lumina_core.order_gatekeeper import (  # noqa: F401 — monkeypatch surface
    is_stale_contract_symbol,
    roll_stale_contract_symbol,
)
from .market_data_history import MarketDataHistoryMixin
from .market_data_ingest import MarketDataIngestCore

__all__ = ["MarketDataIngestService", "MarketDataService"]


@dataclass(slots=True)
class MarketDataIngestService(MarketDataHistoryMixin, MarketDataIngestCore):
    """Websocket and historical market-data ingestion backed by MarketDataManager."""


# Legacy / docs alias — same public type.
MarketDataService = MarketDataIngestService
