"""
Tests for RlBiasApplier (D2 sub-slice 10: RL bias extraction + dupe hygiene with pre_dream).
Per test-scaffolding: @pytest.mark.unit, given-when-then, fail-closed/best-effort, monkeypatch.
"""

import pytest
from types import SimpleNamespace

from lumina_core.engine.rl_bias_applier import RlBiasApplier


@pytest.mark.unit
def test_rl_bias_applier_override_and_mult_adj_and_shadow_mut(monkeypatch):
    """Given applier with mock engine (rl_env/ppo + guard), when apply_bias(HOLD, dream, 1.0, 1.0), then overrides to BUY, mults adj, shadow mut, returns tuple; 'MANUAL_SMOKE_SUB10_SUCCESS'."""
    shadow_state = {}
    calls = {"guard": 0}

    def fake_predict(_obs):
        return {"signal": 1, "qty_pct": 0.5, "stop_mult": 1.5}

    def fake_apply(rl_action, baseline_signal, regime, shadow_state):
        calls["guard"] += 1
        return {"signal": 1, "qty_pct": 0.5, "stop_mult": 1.5}, {"streak": 1}

    app = SimpleNamespace(
        engine=SimpleNamespace(
            rl_env=SimpleNamespace(_get_observation=lambda: {}),
            ppo_trainer=SimpleNamespace(predict_action=fake_predict),
            rl_shadow_state=shadow_state,
        ),
        logger=SimpleNamespace(info=lambda *a, **k: None, debug=lambda *a, **k: None, error=lambda *a, **k: None),
    )
    guard = SimpleNamespace(apply=fake_apply)
    applier = RlBiasApplier(app=app, guardrail=guard)
    dream = {"regime": "TRENDING", "signal": "HOLD"}
    sig, act, qm, sm = applier.apply_bias(
        current_signal="HOLD",
        dream_snapshot=dream,
        qty_multiplier=1.0,
        stop_widen_multiplier=1.0,
        baseline_signal="HOLD",
    )
    assert sig == "BUY"
    assert act is not None and act.get("signal") == 1
    assert abs(qm - 0.5) < 0.01
    assert abs(sm - 1.5) < 0.01
    assert dream.get("signal") == "BUY"
    assert calls["guard"] == 1
    assert "streak" in getattr(app.engine, "rl_shadow_state", {})
    print("MANUAL_SMOKE_SUB10_SUCCESS")


@pytest.mark.unit
def test_predict_cycle_signal_maps_buy_without_guardrail():
    app = SimpleNamespace(
        engine=SimpleNamespace(
            rl_env=SimpleNamespace(_get_observation=lambda: {}),
            ppo_trainer=SimpleNamespace(predict_action=lambda _obs: {"signal": 1}),
        ),
        logger=SimpleNamespace(debug=lambda *a, **k: None),
    )
    sig, action = RlBiasApplier(app=app).predict_cycle_signal()
    assert sig == "BUY"
    assert action is not None
    print("MANUAL_SMOKE_SUB20_RL_PREDICT_SUCCESS")


@pytest.mark.unit
def test_predict_cycle_signal_fail_closed_hold_on_missing_rl():
    app = SimpleNamespace(
        engine=SimpleNamespace(rl_env=None, ppo_trainer=None),
        logger=SimpleNamespace(debug=lambda *a, **k: None),
    )
    sig, action = RlBiasApplier(app=app).predict_cycle_signal()
    assert sig == "HOLD"
    assert action is None


@pytest.mark.unit
def test_rl_bias_applier_no_rl_fallback_original_signal():
    """Given no rl_env/ppo, when apply, then returns original signal + None + original mults; fail-closed/best-effort."""
    app = SimpleNamespace(
        engine=SimpleNamespace(rl_env=None, ppo_trainer=None, rl_shadow_state={}),
        logger=SimpleNamespace(info=lambda *a, **k: None),
    )
    applier = RlBiasApplier(app=app)
    dream = {"regime": "NEUTRAL", "signal": "HOLD"}
    sig, act, qm, sm = applier.apply_bias(
        current_signal="HOLD",
        dream_snapshot=dream,
        qty_multiplier=1.0,
        stop_widen_multiplier=1.0,
    )
    assert sig == "HOLD"
    assert act is None
    assert abs(qm - 1.0) < 0.01
    assert abs(sm - 1.0) < 0.01


@pytest.mark.unit
def test_rl_bias_applier_error_path_logs_and_returns_original(monkeypatch):
    """Given ppo that raises, when apply, then except path (RUNTIME_RL_012 logged), returns original signal; fail-closed/best-effort."""
    def bad_predict(_o):
        raise RuntimeError("ppo boom")

    app = SimpleNamespace(
        engine=SimpleNamespace(
            rl_env=SimpleNamespace(_get_observation=lambda: {}),
            ppo_trainer=SimpleNamespace(predict_action=bad_predict),
            rl_shadow_state={},
        ),
        logger=SimpleNamespace(info=lambda *a, **k: None, debug=lambda *a, **k: None, error=lambda *a, **k: None),
    )
    applier = RlBiasApplier(app=app)
    dream = {"regime": "NEUTRAL", "signal": "SELL"}
    sig, act, qm, sm = applier.apply_bias(
        current_signal="SELL",
        dream_snapshot=dream,
        qty_multiplier=1.0,
        stop_widen_multiplier=1.0,
    )
    assert sig == "SELL"
    assert act is None


# Extend existing RL tests (pre_dream + evolution_risk_proposal) style: the thin in runtime_workers now delegates; existing tests that mock ppo/guard continue to pass via applier (integration via supervisor-mock in full run).