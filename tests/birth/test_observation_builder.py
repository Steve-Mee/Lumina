from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from lumina_core.birth.tick_enricher import enrich_ticks_for_sim
from lumina_core.rl.observation_builder import OBSERVATION_DIM, build_observation_vector, regime_scalar


@pytest.mark.unit
def test_observation_builder_trend_slots_from_enriched_ticks() -> None:
    engine = SimpleNamespace(
        detect_market_regime=lambda _df: "NEUTRAL",
        market_data=SimpleNamespace(get_tape_snapshot=lambda: {}),
        get_current_dream_snapshot=lambda: {},
        AI_DRAWN_FIBS={},
        world_model={},
    )
    raw = [{"last": 5000.0 + i * 2.0, "volume": 100} for i in range(100)]
    data = enrich_ticks_for_sim(raw)
    row = data[80]
    obs = build_observation_vector(
        row=row,
        engine=engine,
        data=data,
        idx=80,
        position=0,
        qty=0,
        entry_price=0.0,
        equity=50_000.0,
        drawdown=0.0,
        rolling_sharpe=0.0,
        trade_mode="birth",
    )
    assert obs.shape == (OBSERVATION_DIM,)
    assert obs[1] == pytest.approx(row["trend_regime_strength"])
    assert obs[35] == pytest.approx(row["trend_slope_5"])
    assert obs[42] == pytest.approx(row["trend_atr_ratio"])
    assert obs[1] > 0


@pytest.mark.unit
def test_observation_builder_returns_43_dim_vector() -> None:
    engine = SimpleNamespace(
        detect_market_regime=lambda _df: "NEUTRAL",
        market_data=SimpleNamespace(get_tape_snapshot=lambda: {}),
        get_current_dream_snapshot=lambda: {},
        AI_DRAWN_FIBS={},
        world_model={},
    )
    data = [{"last": 5000.0, "close": 5000.0, "regime": "TREND_UP", "bible_confluence": 0.7} for _ in range(80)]
    obs = build_observation_vector(
        row=data[60],
        engine=engine,
        data=data,
        idx=60,
        position=1,
        qty=1,
        entry_price=4990.0,
        equity=50_000.0,
        drawdown=0.01,
        rolling_sharpe=0.5,
        dna_hash="abc",
    )
    assert obs.shape == (OBSERVATION_DIM,)
    assert obs.dtype == np.float32


@pytest.mark.unit
def test_regime_scalar_maps_trend_up() -> None:
    assert regime_scalar("TREND_UP") == 1.0


@pytest.mark.unit
def test_bible_slots_populated_from_tick() -> None:
    engine = SimpleNamespace(
        detect_market_regime=lambda _df: "NEUTRAL",
        market_data=SimpleNamespace(get_tape_snapshot=lambda: {}),
        get_current_dream_snapshot=lambda: {},
        AI_DRAWN_FIBS={},
        world_model={},
    )
    row = {
        "last": 5000.0,
        "close": 5000.0,
        "bible_confluence": 0.88,
        "bible_news_proximity": 0.2,
        "bible_session_phase": 0.5,
        "bible_mtf_bias": -0.3,
    }
    obs = build_observation_vector(
        row=row,
        engine=engine,
        data=[row],
        idx=0,
        position=0,
        qty=0,
        entry_price=0.0,
        equity=50_000.0,
        drawdown=0.0,
        rolling_sharpe=0.0,
    )
    assert obs[24] == pytest.approx(0.88)
    assert obs[25] == pytest.approx(0.2)
