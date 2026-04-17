#!/usr/bin/env python3
"""Quick validation test for EmotionalTwinAgent"""

from lumina_core.engine.emotional_twin_agent import EmotionalTwinAgent
from lumina_core.runtime_context import RuntimeContext
from unittest.mock import MagicMock
from types import SimpleNamespace
import pandas as pd
import numpy as np

# Create minimal mock engine with necessary attributes
mock_engine = SimpleNamespace(
    logger=MagicMock(),
    current_market_state={"price": 100.5, "regime": "uptrend", "confidence": 0.85},
    get_current_dream_snapshot=MagicMock(
        return_value={"confidence": 0.85, "confluence_score": 75, "consensus": "LONG", "target_price": 101.5}
    ),
    account_equity=10000,
    account_balance=1000,
    current_price=100.5,
    live_quotes=[{"last": 100.5}],
    ohlc_1min=pd.DataFrame({"close": np.random.randn(100) * 0.5 + 100.5}),
    pnl_history=[100, 150, 120, 200, 180],
    trade_log=[{"ts": "2026-04-04T10:00:00"}],
    sim_peak=10500,
    detect_market_regime=MagicMock(return_value="uptrend"),
)

# Create context with mock engine
ctx = RuntimeContext(engine=mock_engine)
twin = EmotionalTwinAgent(ctx)
print("✅ EmotionalTwinAgent loaded")
print("FOMO/Tilt/Boredom/Revenge simulation ready")
obs = twin._get_observation()
print(f"\nObservation: {obs}")
bias = twin._calculate_bias(obs)
print(f"\nBias example: {bias}")
print("\n✅ All systems operational!")
