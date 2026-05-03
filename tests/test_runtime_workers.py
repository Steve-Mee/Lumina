from types import SimpleNamespace
from contextlib import nullcontext
from datetime import datetime
from typing import Any, cast

import numpy as np
import pandas as pd
import pytest

from lumina_core import runtime_workers
from lumina_core.engine import EngineConfig
from lumina_core.engine.lumina_engine import LuminaEngine
from lumina_core.risk.final_arbitration import FinalArbitration
from lumina_core.risk.risk_policy import RiskPolicy
from lumina_core.runtime_context import RuntimeContext


def test_runtime_workers_exports_expected_callables():
    assert callable(runtime_workers.pre_dream_daemon)
    assert callable(runtime_workers.voice_listener_thread)
    assert callable(runtime_workers.supervisor_loop)


def test_runtime_context_delegates_engine_surface():
    # RuntimeContext is an engine adapter and should expose engine attributes.
    app = SimpleNamespace(value=1)
    engine = cast(Any, LuminaEngine)(config=EngineConfig())
    ctx = RuntimeContext(engine=engine, app=cast(Any, app))
    assert cast(Any, ctx.app) is app
    assert ctx.fast_path is engine.fast_path


def test_pre_dream_daemon_applies_emotional_twin_correction(monkeypatch):
    class TwinSpy:
        def __init__(self):
            self.calls = 0

        def apply_correction(self, dream_json):
            self.calls += 1
            patched = dict(dream_json)
            patched["signal"] = "HOLD"
            return patched

    twin = TwinSpy()

    async def _consensus(*_args, **_kwargs):
        return {"signal": "BUY", "confidence": 0.8, "reason": "ok"}

    async def _meta(*_args, **_kwargs):
        return {"meta_reasoning": "meta", "meta_score": 0.6, "counterfactuals": []}

    app = SimpleNamespace(
        live_data_lock=nullcontext(),
        live_quotes=[{"last": 5000.0}],
        ohlc_1min=pd.DataFrame(
            {
                "open": [5000.0] * 120,
                "high": [5001.0] * 120,
                "low": [4999.0] * 120,
                "close": [5000.0] * 120,
            }
        ),
        detect_market_regime=lambda _df: "TRENDING",
        regime_history=[],
        detect_market_structure=lambda _df: {},
        engine=SimpleNamespace(
            fast_path=SimpleNamespace(run=lambda _df, _p, _r: {"used_llm": True}),
            config=SimpleNamespace(vision_model="dummy", news_impact_multipliers={}),
            emotional_twin=twin,
            rl_env=None,
            ppo_trainer=None,
        ),
        pnl_history=[],
        np=np,
        calculate_dynamic_confluence=lambda _r, _w: 0.7,
        get_mtf_snapshots=lambda: "mtf",
        detect_swing_and_fibs=lambda: (None, None, {}),
        generate_price_action_summary=lambda: "pa",
        generate_multi_tf_chart=lambda: "abc",
        update_live_chart=lambda *_a, **_k: None,
        multi_agent_consensus=_consensus,
        retrieve_relevant_experiences=lambda *_a, **_k: [],
        meta_reasoning_and_counterfactuals=_meta,
        update_world_model=lambda *_a, **_k: {
            "macro": {"vix": 1.0, "dxy": 1.0, "ten_year_yield": 1.0},
            "micro": {"regime": "TRENDING", "orderflow_bias": "NEUTRAL"},
        },
        get_high_impact_news=lambda: {"events": [], "overall_sentiment": "neutral", "impact": "medium"},
        resolve_news_multiplier=lambda *_a, **_k: 1.0,
        set_current_dream_value=lambda *_a, **_k: None,
        infer_json=lambda *_a, **_k: {
            "signal": "BUY",
            "confluence_score": 0.8,
            "reason": "vision",
            "chosen_strategy": "event_driven",
            "fib_levels_drawn": {},
            "narrative_reasoning": "hello",
        },
        set_current_dream_fields=lambda *_a, **_k: None,
        get_current_dream_snapshot=lambda: {
            "chosen_strategy": "event_driven",
            "signal": "BUY",
            "confluence_score": 0.8,
        },
        AI_DRAWN_FIBS={},
        speak=lambda *_a, **_k: None,
        store_experience_to_vector_db=lambda *_a, **_k: None,
        logger=SimpleNamespace(debug=lambda *_a, **_k: None, error=lambda *_a, **_k: None),
    )

    monkeypatch.setattr(runtime_workers.time, "sleep", lambda *_a, **_k: (_ for _ in ()).throw(SystemExit()))

    with pytest.raises(SystemExit):
        runtime_workers.pre_dream_daemon(cast(Any, app))

    assert twin.calls >= 1


def test_supervisor_loop_applies_emotional_twin_correction(monkeypatch):
    class TwinSpy:
        def __init__(self):
            self.calls = 0

        def apply_correction(self, dream_snapshot):
            self.calls += 1
            patched = dict(dream_snapshot)
            patched["signal"] = "HOLD"
            return patched

    twin = TwinSpy()

    app = SimpleNamespace(
        live_data_lock=nullcontext(),
        live_quotes=[{"last": 5000.0}],
        ohlc_1min=pd.DataFrame({"close": [5000.0]}),
        fetch_account_balance=lambda: None,
        account_equity=50000.0,
        account_balance=50000.0,
        save_state=lambda: None,
        get_current_dream_snapshot=lambda: {
            "signal": "HOLD",
            "confluence_score": 0.8,
            "regime": "NEUTRAL",
            "stop": 4990.0,
            "target": 5010.0,
        },
        set_current_dream_fields=lambda *_a, **_k: None,
        is_market_open=lambda: False,
        sim_position_qty=0,
        sim_entry_price=0.0,
        open_pnl=0.0,
        realized_pnl_today=0.0,
        calculate_adaptive_risk_and_qty=lambda *_a, **_k: 1,
        place_order=lambda *_a, **_k: False,
        pnl_history=[],
        equity_curve=[50000.0],
        logger=SimpleNamespace(info=lambda *_a, **_k: None, error=lambda *_a, **_k: None, debug=lambda *_a, **_k: None),
        engine=SimpleNamespace(
            config=SimpleNamespace(
                trade_mode="paper",
                drawdown_kill_percent=8.0,
                status_print_interval_sec=9999.0,
                min_confluence=0.75,
            ),
            emotional_twin=twin,
            infinite_simulator=None,
            rl_env=None,
            ppo_trainer=None,
        ),
        np=np,
    )

    def _raise_stop(*_a, **_k):
        raise StopIteration()

    monkeypatch.setattr(runtime_workers.time, "sleep", _raise_stop)

    with pytest.raises(StopIteration):
        runtime_workers.supervisor_loop(cast(Any, app))

    assert twin.calls >= 1


def test_supervisor_loop_real_close_marks_reconciler_pending(monkeypatch):
    class ReconcilerSpy:
        def __init__(self):
            self.calls: list[dict] = []

        def mark_closing(self, **kwargs):
            self.calls.append(dict(kwargs))
            return "reconcile-1"

    reconciler = ReconcilerSpy()
    direct_push_calls: list[dict] = []

    monkeypatch.setattr(
        runtime_workers, "_push_trader_league_trade", lambda *_a, **kwargs: direct_push_calls.append(dict(kwargs))
    )

    def _raise_stop(*_a, **_k):
        raise StopIteration()

    monkeypatch.setattr(runtime_workers.time, "sleep", _raise_stop)

    app = SimpleNamespace(
        live_data_lock=nullcontext(),
        live_quotes=[{"last": 5005.0}],
        ohlc_1min=pd.DataFrame({"close": [5005.0]}),
        fetch_account_balance=lambda: None,
        account_equity=50000.0,
        account_balance=50000.0,
        save_state=lambda: None,
        get_current_dream_snapshot=lambda: {
            "signal": "HOLD",
            "confluence_score": 0.8,
            "regime": "NEUTRAL",
            "stop": 4990.0,
            "target": 5010.0,
        },
        set_current_dream_fields=lambda *_a, **_k: None,
        is_market_open=lambda: False,
        sim_position_qty=0,
        sim_entry_price=0.0,
        open_pnl=0.0,
        realized_pnl_today=125.0,
        calculate_adaptive_risk_and_qty=lambda *_a, **_k: 1,
        place_order=lambda *_a, **_k: False,
        pnl_history=[],
        equity_curve=[50000.0],
        logger=SimpleNamespace(info=lambda *_a, **_k: None, error=lambda *_a, **_k: None, debug=lambda *_a, **_k: None),
        trade_reconciler=reconciler,
        engine=SimpleNamespace(
            config=SimpleNamespace(
                trade_mode="real",
                drawdown_kill_percent=8.0,
                status_print_interval_sec=9999.0,
                min_confluence=0.75,
                instrument="MES JUN26",
            ),
            emotional_twin=None,
            infinite_simulator=None,
            rl_env=None,
            ppo_trainer=None,
            live_position_qty=2,
            live_trade_signal="BUY",
            last_entry_price=5000.0,
            last_realized_pnl_snapshot=100.0,
        ),
        np=np,
    )

    with pytest.raises(StopIteration):
        runtime_workers.supervisor_loop(cast(Any, app))

    assert len(reconciler.calls) == 1
    call = reconciler.calls[0]
    assert call["symbol"] == "MES JUN26"
    assert call["signal"] == "BUY"
    assert call["quantity"] == 2
    assert call["detected_exit_price"] == 5005.0
    assert call["expected_pnl"] == 25.0
    assert direct_push_calls == []
    assert app.engine.live_position_qty == 0
    assert app.engine.live_trade_signal == "HOLD"


def test_supervisor_loop_runs_swarm_only_on_five_minute_boundary(monkeypatch):
    class SwarmSpy:
        def __init__(self):
            self.run_calls = 0
            self.apply_calls = 0

        def run_swarm_cycle(self):
            self.run_calls += 1
            return {"global_regime": "TRENDING", "allocation": {"MES JUN26": 1.0}}

        def apply_to_primary_dream(self):
            self.apply_calls += 1

        def generate_dashboard_plot(self):
            return None

    class FakeDateTime:
        @classmethod
        def now(cls):
            return datetime(2026, 4, 4, 12, 10, 5)

    swarm = SwarmSpy()
    recorded_updates = []

    app = SimpleNamespace(
        live_data_lock=nullcontext(),
        live_quotes=[{"last": 5000.0}],
        ohlc_1min=pd.DataFrame({"close": [5000.0]}),
        fetch_account_balance=lambda: None,
        account_equity=50000.0,
        account_balance=50000.0,
        save_state=lambda: None,
        get_current_dream_snapshot=lambda: {
            "signal": "HOLD",
            "confluence_score": 0.8,
            "regime": "NEUTRAL",
            "stop": 4990.0,
            "target": 5010.0,
        },
        set_current_dream_fields=lambda updates: recorded_updates.append(dict(updates)),
        set_current_dream_value=lambda *_a, **_k: None,
        is_market_open=lambda: False,
        sim_position_qty=0,
        sim_entry_price=0.0,
        open_pnl=0.0,
        realized_pnl_today=0.0,
        calculate_adaptive_risk_and_qty=lambda *_a, **_k: 1,
        place_order=lambda *_a, **_k: False,
        pnl_history=[],
        equity_curve=[50000.0],
        logger=SimpleNamespace(info=lambda *_a, **_k: None, error=lambda *_a, **_k: None, debug=lambda *_a, **_k: None),
        engine=SimpleNamespace(
            config=SimpleNamespace(
                trade_mode="paper",
                drawdown_kill_percent=8.0,
                status_print_interval_sec=9999.0,
                min_confluence=0.75,
                instrument="MES JUN26",
            ),
            emotional_twin=None,
            infinite_simulator=None,
            rl_env=None,
            ppo_trainer=None,
            swarm=swarm,
        ),
        swarm_manager=swarm,
        np=np,
    )

    monkeypatch.setattr(runtime_workers, "datetime", FakeDateTime)

    def _raise_stop(*_a, **_k):
        raise StopIteration()

    monkeypatch.setattr(runtime_workers.time, "sleep", _raise_stop)

    with pytest.raises(StopIteration):
        runtime_workers.supervisor_loop(cast(Any, app))

    assert swarm.run_calls == 1


def test_supervisor_loop_paper_submit_routes_via_broker(monkeypatch):
    broker_calls: list[object] = []

    class BrokerSpy:
        def submit_order(self, order):
            broker_calls.append(order)
            return SimpleNamespace(accepted=True)

    app = SimpleNamespace(
        live_data_lock=nullcontext(),
        live_quotes=[{"last": 5000.0}],
        ohlc_1min=pd.DataFrame({"close": [5000.0]}),
        fetch_account_balance=lambda: None,
        account_equity=50000.0,
        account_balance=50000.0,
        save_state=lambda: None,
        get_current_dream_snapshot=lambda: {
            "signal": "BUY",
            "confluence_score": 0.9,
            "regime": "NEUTRAL",
            "stop": 4990.0,
            "target": 5010.0,
        },
        set_current_dream_fields=lambda *_a, **_k: None,
        set_current_dream_value=lambda *_a, **_k: None,
        is_market_open=lambda: True,
        sim_position_qty=0,
        sim_entry_price=0.0,
        open_pnl=0.0,
        realized_pnl_today=0.0,
        calculate_adaptive_risk_and_qty=lambda *_a, **_k: 2,
        place_order=lambda *_a, **_k: False,
        pnl_history=[],
        equity_curve=[50000.0],
        logger=SimpleNamespace(
            info=lambda *_a, **_k: None,
            error=lambda *_a, **_k: None,
            debug=lambda *_a, **_k: None,
            warning=lambda *_a, **_k: None,
        ),
        engine=SimpleNamespace(
            config=SimpleNamespace(
                trade_mode="paper",
                drawdown_kill_percent=8.0,
                status_print_interval_sec=9999.0,
                min_confluence=0.75,
                instrument="MES JUN26",
            ),
            emotional_twin=None,
            infinite_simulator=None,
            rl_env=None,
            ppo_trainer=None,
            account_equity=50000.0,
            realized_pnl_today=0.0,
            available_margin=42000.0,
            positions_margin_used=8000.0,
            live_position_qty=0,
            get_current_dream_snapshot=lambda: {"regime": "NEUTRAL"},
            risk_controller=SimpleNamespace(
                check_can_trade=lambda *_a, **_k: (True, "ok"),
                state=SimpleNamespace(open_risk_by_symbol={}, margin_tracker=SimpleNamespace(account_equity=50000.0)),
            ),
            final_arbitration=FinalArbitration(
                RiskPolicy(
                    runtime_mode="paper",
                    daily_loss_cap=-1000.0,
                    max_open_risk_per_instrument=500.0,
                    max_total_open_risk=1200.0,
                    max_exposure_per_regime=2000.0,
                    var_95_limit_usd=1200.0,
                    var_99_limit_usd=1800.0,
                    es_95_limit_usd=1500.0,
                    es_99_limit_usd=2200.0,
                    margin_min_confidence=0.6,
                )
            ),
        ),
        container=SimpleNamespace(broker=BrokerSpy()),
        np=np,
    )

    def _raise_stop(*_a, **_k):
        raise StopIteration()

    monkeypatch.setattr(
        runtime_workers,
        "apply_hard_risk_controller_to_signal",
        lambda **kwargs: (str(kwargs.get("signal", "HOLD")), True, "ok"),
    )
    monkeypatch.setattr(
        runtime_workers,
        "apply_agent_policy_gateway",
        lambda **kwargs: {"signal": str(kwargs.get("signal", "HOLD")), "approved": True, "reason": "ok"},
    )
    monkeypatch.setattr(runtime_workers.time, "sleep", _raise_stop)

    with pytest.raises(StopIteration):
        runtime_workers.supervisor_loop(cast(Any, app))

    assert len(broker_calls) == 1
    assert app.sim_position_qty == 2


def test_supervisor_loop_skips_swarm_outside_five_minute_boundary(monkeypatch):
    class SwarmSpy:
        def __init__(self):
            self.run_calls = 0

        def run_swarm_cycle(self):
            self.run_calls += 1
            return {"global_regime": "TRENDING", "allocation": {}}

        def apply_to_primary_dream(self):
            return None

        def generate_dashboard_plot(self):
            return None

    class FakeDateTime:
        @classmethod
        def now(cls):
            return datetime(2026, 4, 4, 12, 11, 5)

    swarm = SwarmSpy()

    app = SimpleNamespace(
        live_data_lock=nullcontext(),
        live_quotes=[{"last": 5000.0}],
        ohlc_1min=pd.DataFrame({"close": [5000.0]}),
        fetch_account_balance=lambda: None,
        account_equity=50000.0,
        account_balance=50000.0,
        save_state=lambda: None,
        get_current_dream_snapshot=lambda: {
            "signal": "HOLD",
            "confluence_score": 0.8,
            "regime": "NEUTRAL",
            "stop": 4990.0,
            "target": 5010.0,
        },
        set_current_dream_fields=lambda *_a, **_k: None,
        set_current_dream_value=lambda *_a, **_k: None,
        is_market_open=lambda: False,
        sim_position_qty=0,
        sim_entry_price=0.0,
        open_pnl=0.0,
        realized_pnl_today=0.0,
        calculate_adaptive_risk_and_qty=lambda *_a, **_k: 1,
        place_order=lambda *_a, **_k: False,
        pnl_history=[],
        equity_curve=[50000.0],
        logger=SimpleNamespace(info=lambda *_a, **_k: None, error=lambda *_a, **_k: None, debug=lambda *_a, **_k: None),
        engine=SimpleNamespace(
            config=SimpleNamespace(
                trade_mode="paper",
                drawdown_kill_percent=8.0,
                status_print_interval_sec=9999.0,
                min_confluence=0.75,
                instrument="MES JUN26",
            ),
            emotional_twin=None,
            infinite_simulator=None,
            rl_env=None,
            ppo_trainer=None,
            swarm=swarm,
        ),
        swarm_manager=swarm,
        np=np,
    )

    monkeypatch.setattr(runtime_workers, "datetime", FakeDateTime)

    def _raise_stop(*_a, **_k):
        raise StopIteration()

    monkeypatch.setattr(runtime_workers.time, "sleep", _raise_stop)

    with pytest.raises(StopIteration):
        runtime_workers.supervisor_loop(cast(Any, app))

    assert swarm.run_calls == 0


@pytest.mark.safety_gate
def test_supervisor_loop_real_eod_force_close_flattens_and_holds(monkeypatch):
    flatten_orders: list[object] = []
    place_order_calls = {"count": 0}

    class BrokerSpy:
        def get_positions(self):
            return [SimpleNamespace(symbol="MES JUN26", quantity=2)]

        def submit_order(self, order):
            flatten_orders.append(order)
            return SimpleNamespace(accepted=True, message="ok")

    app = SimpleNamespace(
        live_data_lock=nullcontext(),
        live_quotes=[{"last": 5000.0}],
        ohlc_1min=pd.DataFrame({"close": [5000.0]}),
        fetch_account_balance=lambda: None,
        account_equity=50000.0,
        account_balance=50000.0,
        save_state=lambda: None,
        get_current_dream_snapshot=lambda: {
            "signal": "BUY",
            "confluence_score": 0.9,
            "regime": "NEUTRAL",
            "stop": 4990.0,
            "target": 5010.0,
        },
        set_current_dream_fields=lambda *_a, **_k: None,
        set_current_dream_value=lambda *_a, **_k: None,
        is_market_open=lambda: True,
        sim_position_qty=0,
        sim_entry_price=0.0,
        open_pnl=0.0,
        realized_pnl_today=0.0,
        calculate_adaptive_risk_and_qty=lambda *_a, **_k: 2,
        place_order=lambda *_a, **_k: place_order_calls.__setitem__("count", place_order_calls["count"] + 1),
        pnl_history=[],
        equity_curve=[50000.0],
        logger=SimpleNamespace(
            info=lambda *_a, **_k: None,
            error=lambda *_a, **_k: None,
            debug=lambda *_a, **_k: None,
            warning=lambda *_a, **_k: None,
        ),
        container=SimpleNamespace(broker=BrokerSpy()),
        engine=SimpleNamespace(
            config=SimpleNamespace(
                trade_mode="real",
                drawdown_kill_percent=8.0,
                status_print_interval_sec=9999.0,
                min_confluence=0.75,
                instrument="MES JUN26",
            ),
            emotional_twin=None,
            infinite_simulator=None,
            rl_env=None,
            ppo_trainer=None,
            risk_controller=SimpleNamespace(
                should_force_close_eod=lambda: (True, "within EOD force-close window"),
                check_can_trade=lambda *_a, **_k: (True, "ok"),
            ),
            live_position_qty=0,
            last_entry_price=0.0,
            live_trade_signal="BUY",
            last_realized_pnl_snapshot=0.0,
        ),
        np=np,
    )

    def _raise_stop(*_a, **_k):
        raise StopIteration()

    monkeypatch.setattr(runtime_workers.time, "sleep", _raise_stop)

    with pytest.raises(StopIteration):
        runtime_workers.supervisor_loop(cast(Any, app))

    assert len(flatten_orders) == 1
    flatten = cast(Any, flatten_orders[0])
    assert flatten.side == "SELL"
    assert flatten.quantity == 2
    assert place_order_calls["count"] == 0


def test_enforce_real_eod_force_close_applies_to_sim_real_guard():
    flatten_orders: list[object] = []

    class BrokerSpy:
        def get_positions(self):
            return [SimpleNamespace(symbol="MES JUN26", quantity=1)]

        def submit_order(self, order):
            flatten_orders.append(order)
            return SimpleNamespace(accepted=True, message="ok")

    app = SimpleNamespace(
        engine=SimpleNamespace(
            config=SimpleNamespace(trade_mode="sim_real_guard", instrument="MES JUN26"),
            risk_controller=SimpleNamespace(should_force_close_eod=lambda: (True, "within EOD force-close window")),
            live_position_qty=1,
            last_entry_price=4998.0,
            live_trade_signal="BUY",
        ),
        container=SimpleNamespace(broker=BrokerSpy()),
        logger=SimpleNamespace(warning=lambda *_a, **_k: None, error=lambda *_a, **_k: None),
    )

    activated = runtime_workers._enforce_real_eod_force_close(cast(Any, app), 5000.0)

    assert activated is True
    assert len(flatten_orders) == 1
    assert cast(Any, flatten_orders[0]).metadata["mode"] == "sim_real_guard"


def test_enforce_real_eod_force_close_skips_sim_mode():
    calls = {"get_positions": 0}

    class BrokerSpy:
        def get_positions(self):
            calls["get_positions"] += 1
            return []

    app = SimpleNamespace(
        engine=SimpleNamespace(
            config=SimpleNamespace(trade_mode="sim", instrument="MES JUN26"),
            risk_controller=SimpleNamespace(should_force_close_eod=lambda: (True, "within EOD force-close window")),
        ),
        container=SimpleNamespace(broker=BrokerSpy()),
        logger=SimpleNamespace(warning=lambda *_a, **_k: None, error=lambda *_a, **_k: None),
    )

    activated = runtime_workers._enforce_real_eod_force_close(cast(Any, app), 5000.0)

    assert activated is False
    assert calls["get_positions"] == 0


def test_supervisor_loop_runs_swarm_once_per_boundary_across_multiple_cycles(monkeypatch):
    class SwarmSpy:
        def __init__(self):
            self.run_calls = 0
            self.apply_calls = 0

        def run_swarm_cycle(self):
            self.run_calls += 1
            return {"global_regime": "TRENDING", "allocation": {"MES JUN26": 1.0}}

        def apply_to_primary_dream(self):
            self.apply_calls += 1

        def generate_dashboard_plot(self):
            return None

    class FakeDateTime:
        values = iter(
            [
                datetime(2026, 4, 4, 12, 10, 1),
                datetime(2026, 4, 4, 12, 10, 30),
                datetime(2026, 4, 4, 12, 11, 1),
                datetime(2026, 4, 4, 12, 15, 1),
            ]
        )
        last_value = datetime(2026, 4, 4, 12, 15, 1)

        @classmethod
        def now(cls):
            try:
                cls.last_value = next(cls.values)
            except StopIteration:
                pass
            return cls.last_value

    swarm = SwarmSpy()
    recorded_updates = []
    sleep_calls = {"count": 0}

    def _sleep(*_args, **_kwargs):
        sleep_calls["count"] += 1
        if sleep_calls["count"] >= 4:
            raise StopIteration()

    app = SimpleNamespace(
        live_data_lock=nullcontext(),
        live_quotes=[{"last": 5000.0}],
        ohlc_1min=pd.DataFrame({"close": [5000.0]}),
        fetch_account_balance=lambda: None,
        account_equity=50000.0,
        account_balance=50000.0,
        save_state=lambda: None,
        get_current_dream_snapshot=lambda: {
            "signal": "HOLD",
            "confluence_score": 0.8,
            "regime": "NEUTRAL",
            "stop": 4990.0,
            "target": 5010.0,
        },
        set_current_dream_fields=lambda updates: recorded_updates.append(dict(updates)),
        set_current_dream_value=lambda *_a, **_k: None,
        is_market_open=lambda: False,
        sim_position_qty=0,
        sim_entry_price=0.0,
        open_pnl=0.0,
        realized_pnl_today=0.0,
        calculate_adaptive_risk_and_qty=lambda *_a, **_k: 1,
        place_order=lambda *_a, **_k: False,
        pnl_history=[],
        equity_curve=[50000.0],
        logger=SimpleNamespace(info=lambda *_a, **_k: None, error=lambda *_a, **_k: None, debug=lambda *_a, **_k: None),
        engine=SimpleNamespace(
            config=SimpleNamespace(
                trade_mode="paper",
                drawdown_kill_percent=8.0,
                status_print_interval_sec=999999.0,
                min_confluence=0.75,
                instrument="MES JUN26",
            ),
            emotional_twin=None,
            infinite_simulator=None,
            rl_env=None,
            ppo_trainer=None,
            swarm=swarm,
        ),
        swarm_manager=swarm,
        np=np,
    )

    monkeypatch.setattr(runtime_workers, "datetime", FakeDateTime)
    monkeypatch.setattr(runtime_workers.time, "sleep", _sleep)

    with pytest.raises(StopIteration):
        runtime_workers.supervisor_loop(cast(Any, app))

    assert swarm.run_calls == 2
    assert swarm.apply_calls == 2
    assert len([u for u in recorded_updates if u.get("swarm_regime") == "TRENDING"]) == 2
