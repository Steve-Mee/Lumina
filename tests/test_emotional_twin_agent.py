from __future__ import annotations

from datetime import datetime, timedelta
from types import ModuleType

import pandas as pd

from lumina_core.engine.emotional_twin_agent import EmotionalTwinAgent
from lumina_core.engine import EngineConfig, LuminaEngine


def _build_engine() -> LuminaEngine:
    engine = LuminaEngine(EngineConfig())
    app = ModuleType("emotional_twin_test_app")
    setattr(app, "logger", type("Logger", (), {"error": lambda *args, **kwargs: None})())
    engine.bind_app(app)

    rows = []
    ts0 = datetime(2026, 4, 1, 9, 30)
    for i in range(200):
        px = 5000.0 + (i * 0.25)
        rows.append(
            {
                "timestamp": ts0 + timedelta(minutes=i),
                "open": px,
                "high": px + 0.5,
                "low": px - 0.5,
                "close": px,
                "volume": 2000 + i,
            }
        )
    engine.ohlc_1min = pd.DataFrame(rows)
    return engine


def test_fomo_correction_raises_confluence_threshold():
    engine = _build_engine()
    twin = EmotionalTwinAgent(engine=engine)

    engine.set_current_dream_fields({"signal": "BUY", "confidence": 0.84, "confluence_score": 0.84})
    engine.pnl_history = [120.0, 180.0, 90.0, 70.0, 110.0]
    engine.market_data.cumulative_delta_10 = 8000.0

    result = twin.run_cycle()
    bias = result["emotional_bias"]

    assert bias["fomo_score"] > 0.7
    snap = engine.get_current_dream_snapshot()
    assert float(snap.get("min_confluence_override", 0.0)) > float(engine.config.min_confluence)


def test_tilt_correction_halves_size_and_widens_stop():
    engine = _build_engine()
    twin = EmotionalTwinAgent(engine=engine)

    engine.set_current_dream_fields({"signal": "SELL", "confidence": 0.82, "confluence_score": 0.82})
    engine.pnl_history = [-250.0, -180.0, -140.0, -220.0, -110.0, -90.0]
    engine.equity_curve = [50000.0, 49700.0, 49300.0, 48800.0, 48200.0]
    engine.market_data.cumulative_delta_10 = -900.0

    result = twin.run_cycle()
    bias = result["emotional_bias"]

    assert bias["tilt_score"] > 0.6
    snap = engine.get_current_dream_snapshot()
    assert float(snap.get("position_size_multiplier", 1.0)) == 0.5
    assert float(snap.get("stop_widen_multiplier", 1.0)) > 1.0


def test_boredom_correction_forces_hold_for_15_minutes():
    engine = _build_engine()
    twin = EmotionalTwinAgent(engine=engine)

    engine.set_current_dream_fields({"signal": "BUY", "confidence": 0.78, "confluence_score": 0.78})
    engine.pnl_history = [5.0, -2.0, 3.0, -1.0, 4.0, -3.0, 2.0]
    engine.market_data.cumulative_delta_10 = 20.0

    # Force boredom scenario with low activity.
    obs = twin.build_observation()
    obs["tape_delta"] = 0.0
    bias = twin.infer_emotional_bias(obs)
    bias["boredom_score"] = 0.95
    twin.apply_to_dream(bias, twin.generate_counterfactual_human_decision(obs, bias))

    snap = engine.get_current_dream_snapshot()
    assert snap.get("signal") == "HOLD"
    assert float(snap.get("hold_until_ts", 0.0)) > 0.0
