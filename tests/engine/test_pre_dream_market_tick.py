"""Tests for PreDreamMarketTickService (D2 sub-slice 24)."""

from __future__ import annotations

from types import SimpleNamespace

import pandas as pd
import pytest

from lumina_core.engine.pre_dream_market_tick import PreDreamMarketTickService


def _base_app(*, used_llm: bool = False, rl_signal: str = "HOLD") -> SimpleNamespace:
    regime_history: list = []

    class FastPath:
        def run(self, _df, _price, _regime):
            return {"used_llm": used_llm, "pass_to_llm": used_llm}

    return SimpleNamespace(
        regime_history=regime_history,
        detect_market_regime=lambda _df: "TRENDING",
        detect_market_structure=lambda _df: {"structure": "range"},
        engine=SimpleNamespace(
            fast_path=FastPath(),
            ppo_trainer=None,
            rl_env=None,
        ),
        ppo_trainer=None,
        rl_env=None,
        logger=SimpleNamespace(info=lambda *_a, **_k: None),
        _rl_signal=rl_signal,
    )


@pytest.mark.unit
def test_fast_path_no_llm_should_continue(monkeypatch):
    app = _base_app(used_llm=False)
    calls = {"price": 0}

    def _fetch():
        calls["price"] += 1
        return 5000.0, pd.DataFrame({"close": [5000.0] * 3})

    monkeypatch.setattr(
        "lumina_core.engine.pre_dream_market_tick.PriceDupeResolver.fetch_locked_price_and_ohlc",
        lambda self: _fetch(),
    )
    monkeypatch.setattr(
        "lumina_core.engine.pre_dream_market_tick.RlBiasApplier.predict_cycle_signal",
        lambda self: ("HOLD", None),
    )

    result = PreDreamMarketTickService(app=app).run_tick()
    assert result.should_continue is True
    assert result.price is None
    assert len(app.regime_history) == 1
    assert app.regime_history[0]["regime"] == "TRENDING"
    print("MANUAL_SMOKE_SUB24_FASTPATH_SKIP")


@pytest.mark.unit
def test_rl_buy_forces_llm_branch(monkeypatch):
    app = _base_app(used_llm=False)

    monkeypatch.setattr(
        "lumina_core.engine.pre_dream_market_tick.PriceDupeResolver.fetch_locked_price_and_ohlc",
        lambda self: (5001.0, pd.DataFrame({"close": [5001.0]})),
    )
    monkeypatch.setattr(
        "lumina_core.engine.pre_dream_market_tick.RlBiasApplier.predict_cycle_signal",
        lambda self: ("BUY", {"qty_pct": 0.5, "signal": 1}),
    )

    result = PreDreamMarketTickService(app=app).run_tick()
    assert result.should_continue is False
    assert result.price == 5001.0
    assert result.regime == "TRENDING"
    assert result.rl_signal == "BUY"
    assert result.rl_action == {"qty_pct": 0.5, "signal": 1}
    print("MANUAL_SMOKE_SUB24_LLM_BRANCH")


@pytest.mark.unit
def test_used_llm_fast_path_returns_tick_fields(monkeypatch):
    app = _base_app(used_llm=True)

    monkeypatch.setattr(
        "lumina_core.engine.pre_dream_market_tick.PriceDupeResolver.fetch_locked_price_and_ohlc",
        lambda self: (4999.0, pd.DataFrame({"close": [4999.0, 5000.0]})),
    )
    monkeypatch.setattr(
        "lumina_core.engine.pre_dream_market_tick.RlBiasApplier.predict_cycle_signal",
        lambda self: ("SELL", {"qty_pct": 0.3, "signal": -1}),
    )

    result = PreDreamMarketTickService(app=app).run_tick()
    assert result.should_continue is False
    assert result.structure == {"structure": "range"}
    assert result.df is not None
    assert len(result.df) == 2
