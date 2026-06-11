"""Phase 2 cross-verify manual smokes (Sub10/11/12) per 2026-06-04 perfection remediation plan."""
from types import SimpleNamespace

from lumina_core.engine.price_dupe_resolver import PriceDupeResolver
from lumina_core.engine.rl_bias_applier import RlBiasApplier
from lumina_core.engine.supervisor_phase_state_machine import SupervisorPhaseStateMachine


def sub10():
    shadow_state = {}

    def fake_predict(_obs):
        return {"signal": 1, "qty_pct": 0.5, "stop_mult": 1.5}

    def fake_apply(rl_action, baseline_signal, regime, shadow_state):
        return {"signal": 1, "qty_pct": 0.5, "stop_mult": 1.5}, {"streak": 1}

    app = SimpleNamespace(
        engine=SimpleNamespace(
            rl_env=SimpleNamespace(_get_observation=lambda: {}),
            ppo_trainer=SimpleNamespace(predict_action=fake_predict),
            rl_shadow_state=shadow_state,
        ),
        logger=SimpleNamespace(info=lambda *a, **k: None),
    )
    applier = RlBiasApplier(app=app, guardrail=SimpleNamespace(apply=fake_apply))
    dream = {"regime": "TRENDING", "signal": "HOLD"}
    sig, act, qm, sm = applier.apply_bias(
        current_signal="HOLD",
        dream_snapshot=dream,
        qty_multiplier=1.0,
        stop_widen_multiplier=1.0,
        baseline_signal="HOLD",
    )
    assert sig == "BUY" and act is not None
    print("MANUAL_SMOKE_SUB10_SUCCESS")


def sub12():
    from contextlib import nullcontext

    app = SimpleNamespace(
        live_data_lock=nullcontext(),
        live_quotes=[{"last": 12345.67}],
        ohlc_1min=None,
        engine=SimpleNamespace(
            sim_position_qty=0,
            sim_entry_price=0.0,
            config=SimpleNamespace(instrument="TEST"),
        ),
        INSTRUMENT="TEST",
    )
    price = PriceDupeResolver(app=app).fetch_locked_price()
    assert price == 12345.67
    print("MANUAL_SMOKE_SUB12_PRICE_DUPE_SUCCESS")


def sub11():
    engine = SimpleNamespace(
        config=SimpleNamespace(
            trade_mode="paper",
            instrument="MES",
            min_confluence=0.5,
            drawdown_kill_percent=10.0,
            status_print_interval_sec=9999.0,
        ),
        last_validation=None,
        validator=None,
        emotional_twin=None,
        risk_controller=None,
        local_engine=None,
        infinite_simulator=None,
        swarm=None,
    )
    app = SimpleNamespace(
        engine=engine,
        container=SimpleNamespace(operations_service=None, broker=None),
        INSTRUMENT="MES",
        logger=SimpleNamespace(info=lambda *a, **k: None, warning=lambda *a, **k: None, error=lambda *a, **k: None),
        live_data_lock=type("Lock", (), {"__enter__": lambda s: None, "__exit__": lambda *a: None})(),
        get_current_dream_snapshot=lambda: {"signal": "HOLD", "confluence_score": 0.0},
        set_current_dream_fields=lambda d: None,
        is_market_open=lambda: True,
        calculate_adaptive_risk_and_qty=lambda *a, **k: 0,
        sim_position_qty=0,
        account_equity=100000.0,
        account_balance=100000.0,
        open_pnl=0.0,
        pnl_history=[],
        save_state=lambda: None,
        realized_pnl_today=0.0,
    )
    sm = SupervisorPhaseStateMachine(app=app, engine=engine)
    res = sm.advance_or_tick(5000.0, dream_snapshot={"signal": "HOLD"})
    assert res["signal"] == "HOLD"
    print("MANUAL_SMOKE_SUB11_REMEDIATION_SUCCESS")


if __name__ == "__main__":
    sub10()
    sub12()
    sub11()
    import lumina_core.runtime_workers as rw

    print(
        "IMPORT_OK",
        hasattr(rw, "RlBiasApplier"),
        hasattr(rw, "PriceDupeResolver"),
        hasattr(rw, "SupervisorPhaseStateMachine"),
    )
    print("PHASE2_ALL_MANUAL_SMOKES_OK")
