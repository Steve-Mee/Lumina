"""lumina_core.engine.backtest — Realistic backtesting primitives.

Public surface:
  - OrderBookReplayV2       realistic ATR/regime/time-of-day slippage
  - DynamicSlippageModel    per-bar composite slippage (spread + impact + bounce)
  - PurgedWalkForwardCV     embargo-gap walk-forward cross-validator
  - CombinatorialPurgedCV   CPCV with Probability of Backtest Overfitting
  - RealityGapTracker       rolling SIM vs REAL performance divergence monitor
  - BacktestRealismEngine   top-level integration class used by BacktesterEngine
"""

from lumina_core.engine.backtest.order_book import OrderBookReplayV2, DynamicSlippageModel
from lumina_core.engine.backtest.cross_validation import PurgedWalkForwardCV, CombinatorialPurgedCV
from lumina_core.engine.backtest.reality_gap import RealityGapTracker

__all__ = [
    "OrderBookReplayV2",
    "DynamicSlippageModel",
    "PurgedWalkForwardCV",
    "CombinatorialPurgedCV",
    "RealityGapTracker",
]
