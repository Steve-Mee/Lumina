from __future__ import annotations

from types import SimpleNamespace

import pytest

from lumina_core.birth.tick_enricher import enrich_ticks_for_sim
from lumina_core.rl.observation_builder import OBSERVATION_DIM, build_observation_vector


@pytest.mark.unit
def test_bible_observation_slots_reflect_tick_regime() -> None:
    ticks = enrich_ticks_for_sim(
        [
            {"last": 5000.0 + i * 2.0, "volume": 100, "source": "real"}
            for i in range(80)
        ]
    )
    row = ticks[60]
    row["bible_confluence"] = 0.75
    row["bible_news_proximity"] = 0.1
    row["bible_session_phase"] = 0.6
    row["bible_mtf_bias"] = 0.4

    engine = SimpleNamespace(
        detect_market_regime=lambda _df: "NEUTRAL",
        market_data=SimpleNamespace(get_tape_snapshot=lambda: {}),
        get_current_dream_snapshot=lambda: {},
        AI_DRAWN_FIBS={},
        world_model={},
    )
    obs = build_observation_vector(
        row=row,
        engine=engine,
        data=ticks,
        idx=60,
        position=0,
        qty=0,
        entry_price=0.0,
        equity=50_000.0,
        drawdown=0.0,
        rolling_sharpe=0.0,
    )
    assert obs.shape == (OBSERVATION_DIM,)
    assert obs[24] == pytest.approx(0.75)
    assert obs[1] != 0.0 or "TREND" in str(row.get("regime", "")).upper()
