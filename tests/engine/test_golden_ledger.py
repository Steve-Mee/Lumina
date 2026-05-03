from __future__ import annotations

import logging
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from types import ModuleType
from typing import Any, cast

import pytest

from lumina_core.broker.broker_bridge import Order, PaperBroker
from lumina_core.engine import EngineConfig, TradeReconciler
from lumina_core.engine.golden_ledger import (
    realized_close_from_broker_fill,
    round_turn_realized_from_two_fills,
)
from lumina_core.engine.lumina_engine import LuminaEngine
from lumina_core.engine.valuation_engine import ValuationEngine
from lumina_core.risk.final_arbitration import FinalArbitration
from lumina_core.risk.risk_policy import RiskPolicy


def test_realized_close_from_broker_fill_mes_long_close() -> None:
    ve = ValuationEngine()
    leg = realized_close_from_broker_fill(
        valuation_engine=ve,
        symbol="MES JUN26",
        entry_price=5000.0,
        exit_fill_price=5001.5,
        position_signal="BUY",
        quantity=2,
        exit_commission=1.25,
        reference_price_for_slippage_ticks=5002.0,
    )
    gross = ve.pnl_dollars(
        symbol="MES JUN26",
        entry_price=5000.0,
        exit_price=5001.5,
        side=1,
        quantity=2,
    )
    assert leg.gross_pnl == pytest.approx(float(gross))
    assert leg.realized_net == pytest.approx(float(gross) - 1.25)


def test_round_turn_two_fills_commissions_subtracted() -> None:
    ve = ValuationEngine()
    net = round_turn_realized_from_two_fills(
        valuation_engine=ve,
        symbol="MES JUN26",
        entry_fill_price=5000.0,
        exit_fill_price=5001.0,
        open_side="BUY",
        quantity=1,
        entry_commission=0.5,
        exit_commission=0.75,
    )
    gross = ve.pnl_dollars(
        symbol="MES JUN26",
        entry_price=5000.0,
        exit_price=5001.0,
        side=1,
        quantity=1,
    )
    assert net == pytest.approx(float(gross) - 0.5 - 0.75)


def _paper_engine_stub() -> Any:
    return SimpleNamespace(
        config=SimpleNamespace(trade_mode="paper"),
        live_data_lock=nullcontext(),
        live_quotes=[{"last": 5000.0}],
        ohlc_1min=[],
        account_balance=50000.0,
        account_equity=50000.0,
        available_margin=45000.0,
        positions_margin_used=5000.0,
        realized_pnl_today=0.0,
        risk_controller=SimpleNamespace(
            state=SimpleNamespace(open_risk_by_symbol={}, margin_tracker=SimpleNamespace(account_equity=50000.0))
        ),
        get_current_dream_snapshot=lambda: {"regime": "NEUTRAL"},
        equity_snapshot_provider=SimpleNamespace(
            get_snapshot=lambda: SimpleNamespace(
                ok=True,
                is_fresh=True,
                reason_code="ok",
                source="test",
                equity_usd=50_000.0,
                available_margin_usd=40_000.0,
                used_margin_usd=10_000.0,
                age_seconds=0.2,
            )
        ),
        final_arbitration=FinalArbitration(
            RiskPolicy(
                runtime_mode="paper",
                daily_loss_cap=-1000.0,
                max_open_risk_per_instrument=500.0,
                max_total_open_risk=3000.0,
                max_exposure_per_regime=2000.0,
                var_95_limit_usd=1200.0,
                var_99_limit_usd=1800.0,
                es_95_limit_usd=1500.0,
                es_99_limit_usd=2200.0,
                margin_min_confidence=0.6,
            )
        ),
    )


def test_paper_broker_round_turn_position_netting(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("lumina_core.broker.broker_bridge.random.gauss", lambda _mu, _sigma: 0.0)
    broker = PaperBroker(engine=_paper_engine_stub())
    sym = "MES JUN26"
    assert broker.submit_order(
        Order(symbol=sym, side="BUY", quantity=1, metadata={"skip_admission_chain_recheck": True})
    ).accepted
    pos1 = broker.get_positions()
    assert len(pos1) == 1
    assert pos1[0].quantity > 0
    fills_after_buy = broker.get_fills()
    assert broker.submit_order(
        Order(symbol=sym, side="SELL", quantity=1, metadata={"skip_admission_chain_recheck": True})
    ).accepted
    assert broker.get_positions() == []
    exit_fill = broker.last_fill_for_symbol(sym)
    assert exit_fill is not None
    entry_fill = fills_after_buy[-1]
    ve = ValuationEngine()
    pnl = round_turn_realized_from_two_fills(
        valuation_engine=ve,
        symbol=sym,
        entry_fill_price=float(entry_fill.price),
        exit_fill_price=float(exit_fill.price),
        open_side="BUY",
        quantity=1,
        entry_commission=float(entry_fill.commission),
        exit_commission=float(exit_fill.commission),
    )
    assert isinstance(pnl, float)


def _reconciler_engine(tmp_path: Path) -> tuple[Any, SimpleNamespace]:
    cfg = EngineConfig(
        state_file=tmp_path / "state.json",
        thought_log=tmp_path / "thought_log.jsonl",
        bible_file=tmp_path / "bible.json",
        live_jsonl=tmp_path / "live.jsonl",
        trade_mode="real",
        reconcile_fills=True,
        reconciliation_method="websocket",
        reconciliation_timeout_seconds=0.0,
        trade_reconciler_audit_log=tmp_path / "trade_reconcile_audit.jsonl",
        trade_reconciler_status_file=tmp_path / "trade_reconcile_status.json",
    )
    engine = cast(Any, LuminaEngine)(config=cfg)
    pushes: list[dict[str, Any]] = []
    app = SimpleNamespace(
        logger=logging.getLogger("golden-ledger-test"),
        push_traderleague_trade=lambda **kwargs: pushes.append(dict(kwargs)),
        publish_traderleague_trade_close=lambda **_k: None,
        log_thought=lambda *_a, **_k: None,
    )
    engine.bind_app(cast(ModuleType, app))
    app.pushes = pushes
    return engine, app


def test_reconciler_timeout_does_not_push_pnl(tmp_path: Path) -> None:
    engine, app = _reconciler_engine(tmp_path)
    rec = TradeReconciler(engine)
    rec.mark_closing(
        symbol="MES JUN26",
        signal="BUY",
        entry_price=5000.0,
        detected_exit_price=5002.0,
        quantity=1,
        expected_pnl=99.0,
        reflection={},
    )
    rec._flush_timeouts()
    assert app.pushes == []


def test_reconciler_fill_pnl_matches_golden_ledger(tmp_path: Path) -> None:
    from datetime import datetime, timezone

    engine, app = _reconciler_engine(tmp_path)
    engine.config.reconciliation_timeout_seconds = 60.0
    rec = TradeReconciler(engine)
    rec.mark_closing(
        symbol="MES JUN26",
        signal="BUY",
        entry_price=5000.0,
        detected_exit_price=5002.0,
        quantity=2,
        expected_pnl=50.0,
        reflection={},
    )
    rec.ingest_fill_event(
        {
            "type": "fill",
            "instrument": "MES JUN26",
            "side": "SELL",
            "quantity": 2,
            "fillPrice": 5001.5,
            "commission": 1.25,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "fillId": "golden-fill-1",
        }
    )
    assert len(app.pushes) == 1
    ve = ValuationEngine()
    expected = realized_close_from_broker_fill(
        valuation_engine=ve,
        symbol="MES JUN26",
        entry_price=5000.0,
        exit_fill_price=5001.5,
        position_signal="BUY",
        quantity=2,
        exit_commission=1.25,
        reference_price_for_slippage_ticks=5002.0,
    ).realized_net
    assert float(app.pushes[0]["pnl_dollars"]) == pytest.approx(expected)


def test_rl_close_accounting_vs_training_reward_split() -> None:
    """VAR/ES shaping hits ``training_reward`` while no-trade step keeps model-close accounting at zero."""
    from lumina_core.rl import RLConfig, RLTradingEnvironment

    class _MarketDataStub:
        def get_tape_snapshot(self):
            return {
                "volume_delta": 0.0,
                "avg_volume_delta_10": 0.0,
                "bid_ask_imbalance": 1.0,
                "cumulative_delta_10": 0.0,
            }

    class _RiskControllerStub:
        def __init__(self) -> None:
            self._active_limits = SimpleNamespace(var_95_limit_usd=100.0, es_95_limit_usd=100.0)

        def get_var_es_snapshot(self, *, proposed_risk: float = 0.0):
            del proposed_risk
            return {"var_95_usd": 250.0, "es_95_usd": 300.0}

    class _EngineStub:
        def __init__(self) -> None:
            self.config = SimpleNamespace(
                instrument="MES JUN26",
                trade_mode="sim",
                risk_controller={},
            )
            self.market_data = _MarketDataStub()
            self.AI_DRAWN_FIBS = {}
            self.world_model = {}
            self.risk_controller = _RiskControllerStub()

        def detect_market_regime(self, _df):
            return "NEUTRAL"

        def get_current_dream_snapshot(self):
            return {
                "confidence": 0.0,
                "confluence_score": 0.0,
                "stop": 0.0,
                "target": 0.0,
                "fib_levels": {},
            }

    rows = [{"close": 5000.0 + (i * 0.25)} for i in range(220)]
    cfg = RLConfig(trade_mode="sim", sim_var_penalty_coeff=0.2, sim_es_penalty_coeff=0.3)
    env = RLTradingEnvironment(_EngineStub(), rows, config=cfg)
    env.reset()
    _obs, reward, _done, _trunc, info = env.step([0.0, 0.0, 0.01, 0.02])
    assert float(info["rl_close_accounting_net_usd"]) == pytest.approx(0.0)
    assert float(info["training_reward"]) == float(reward)
    assert float(info["training_reward"]) < 0.0
    assert abs(float(info["rl_close_accounting_net_usd"]) - float(info["training_reward"])) > 1e-9
