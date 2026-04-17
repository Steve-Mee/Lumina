from __future__ import annotations

from collections import deque
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

from lumina_core.engine.emotional_twin_components import (
    _BiasDetector,
    _CalibrationStore,
    _CalibrationTrainer,
    _DecisionCorrector,
    _ObservationBuilder,
)


def _build_context() -> SimpleNamespace:
    return SimpleNamespace(
        get_current_dream_snapshot=lambda: {"signal": "BUY", "confidence": 0.85, "confluence_score": 0.7},
        live_quotes=[{"last": 5100.0}],
        detect_market_regime=lambda _df: "TRENDING",
        ohlc_1min=pd.DataFrame(
            {
                "close": [1.0] * 100,
                "timestamp": pd.date_range("2026-01-01", periods=100, freq="min"),
            }
        ),
        pnl_history=[120.0, 80.0, 100.0, 90.0, 110.0, 95.0],
        trade_log=[{"ts": "2026-04-04T10:00:00"}],
        equity_curve=[50000.0, 49500.0],
        sim_peak=50000.0,
        account_equity=49500.0,
        market_data=SimpleNamespace(cumulative_delta_10=4000.0),
        current_regime_snapshot={"adaptive_policy": {"emotional_twin_sensitivity": 1.0}},
        config=SimpleNamespace(min_confluence=0.7),
    )


def test_observation_builder_returns_expected_keys() -> None:
    context = _build_context()
    builder = _ObservationBuilder(context)

    obs = builder.build()

    assert obs["price"] == 5100.0
    assert obs["regime"] == "TRENDING"
    assert "equity_drawdown" in obs
    assert "time_since_last_trade" in obs


def test_bias_detector_applies_calibration_and_baseline(monkeypatch) -> None:
    context = _build_context()
    detector = _BiasDetector(context)

    monkeypatch.setattr("lumina_core.engine.emotional_twin_components.np.random.normal", lambda _m, _s: 0.0)

    obs = {
        "confidence": 0.86,
        "recent_pnl_mean": 90.0,
        "regime": "TRENDING",
        "tape_delta": 6000.0,
        "equity_drawdown": 0.01,
        "time_since_last_trade": 1.0,
        "last_pnl": 20.0,
    }
    calibration = {
        "fomo_sensitivity": 1.0,
        "tilt_sensitivity": 1.0,
        "boredom_sensitivity": 1.0,
        "revenge_sensitivity": 1.0,
    }
    baselines = {"fomo_base": 0.1, "tilt_base": 0.0, "boredom_base": 0.0, "revenge_base": 0.0}

    bias = detector.compute(obs, calibration, baselines, pnl_len=10)

    assert bias["fomo_score"] > 0.7
    assert bias["tilt_score"] == 0.0


def test_decision_corrector_applies_tilt_and_boredom() -> None:
    context = _build_context()
    corrector = _DecisionCorrector(context)
    dream = {"signal": "BUY", "qty": 10.0, "confluence_score": 0.75, "reason": ""}
    bias = {"fomo_score": 0.0, "tilt_score": 0.8, "boredom_score": 0.9, "revenge_risk": 0.0}

    corrected = corrector.apply(dream, bias)

    assert corrected["signal"] == "HOLD"
    assert corrected["qty"] == 4.0
    assert corrected["stop_widen_multiplier"] == 1.3
    assert corrected["hold_until_ts"] > 0


def test_calibration_trainer_updates_values() -> None:
    trainer = _CalibrationTrainer()
    calibration = {
        "fomo_sensitivity": 1.0,
        "tilt_sensitivity": 1.0,
        "boredom_sensitivity": 1.0,
        "revenge_sensitivity": 1.0,
    }
    memory = deque(
        [
            {"bias": {"tilt_score": 0.7, "fomo_score": 0.8, "boredom_score": 0.9, "revenge_risk": 0.8}},
            {"bias": {"tilt_score": 0.2, "fomo_score": 0.1, "boredom_score": 0.1, "revenge_risk": 0.1}},
        ],
        maxlen=50,
    )

    updated = trainer.train(
        calibration=calibration,
        memory=memory,
        reflections=[{"pnl": -100, "note": "fomo and revenge"}],
        feedback_items=["forced trade from boredom"],
    )

    assert 0.6 <= updated["fomo_sensitivity"] <= 2.0
    assert 0.6 <= updated["tilt_sensitivity"] <= 2.0
    assert 0.6 <= updated["boredom_sensitivity"] <= 2.0
    assert 0.6 <= updated["revenge_sensitivity"] <= 2.0


def test_calibration_store_load_and_save(tmp_path: Path) -> None:
    model_path = tmp_path / "emotional_twin_profile.json"
    calibration = {
        "fomo_sensitivity": 1.0,
        "tilt_sensitivity": 1.0,
        "boredom_sensitivity": 1.0,
        "revenge_sensitivity": 1.0,
    }
    store = _CalibrationStore(model_path)

    store.save(calibration)
    calibration["fomo_sensitivity"] = 0.7
    store.load_into(calibration)

    assert calibration["fomo_sensitivity"] == 1.0
