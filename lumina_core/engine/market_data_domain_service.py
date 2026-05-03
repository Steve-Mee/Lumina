from __future__ import annotations

from dataclasses import dataclass

from .analysis_helpers import detect_candle_patterns, generate_price_action_summary
from .engine_ports import SupportsMarketData


@dataclass(slots=True)
class MarketDataDomainService:
    """Domain-facing market data helpers built on top of MarketDataManager."""

    engine: SupportsMarketData

    def detect_candle_patterns(self, df, tf: str = "1min") -> dict[str, str]:
        return detect_candle_patterns(df, tf)

    def generate_price_action_summary(self) -> str:
        return generate_price_action_summary(self.engine.market_data.copy_ohlc(), self.engine.config.timeframes)


# Backward-compatible alias for callers that still import MarketDataService
# from this domain module.
MarketDataService = MarketDataDomainService
