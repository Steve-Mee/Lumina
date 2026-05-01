"""Bounded context: Data — market data ingestion, tape reading, OHLCV management.

Re-exports from canonical engine-level modules (ADR-002 migration pending).

Current members:
    MarketDataService — live + historical OHLCV data provider
    MarketDataManager — multi-symbol data coordination
    TapeReadingAgent  — order-flow tape analysis
"""

from __future__ import annotations

from lumina_core.engine.market_data_service import MarketDataService
from lumina_core.engine.market_data_manager import MarketDataManager
from lumina_core.engine.tape_reading_agent import TapeReadingAgent

__all__ = [
    "MarketDataService",
    "MarketDataManager",
    "TapeReadingAgent",
]
