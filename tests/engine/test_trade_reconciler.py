from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import cast

from lumina_core.engine import EngineConfig, TradeReconciler
from lumina_core.engine.lumina_engine import LuminaEngine


def _build_engine(tmp_path: Path) -> tuple[LuminaEngine, SimpleNamespace]:
    cfg = EngineConfig(
        state_file=tmp_path / "state.json",
        thought_log=tmp_path / "thought_log.jsonl",
        bible_file=tmp_path / "bible.json",
        live_jsonl=tmp_path / "live.jsonl",
        trade_mode="real",
        reconcile_fills=True,
        reconciliation_method="websocket",
        reconciliation_timeout_seconds=15.0,
        use_real_fill_for_pnl=True,
    )
    engine = LuminaEngine(config=cfg)
    pushes: list[dict] = []
    publishes: list[dict] = []
    thoughts: list[dict] = []
    app = SimpleNamespace(
        logger=logging.getLogger("trade-reconciler-test"),
        push_traderleague_trade=lambda **kwargs: pushes.append(dict(kwargs)),
        publish_traderleague_trade_close=lambda **kwargs: publishes.append(dict(kwargs)),
        log_thought=lambda payload: thoughts.append(dict(payload)),
    )
    engine.bind_app(cast(ModuleType, app))
    app.pushes = pushes
    app.publishes = publishes
    app.thoughts = thoughts
    return engine, app


def test_trade_reconciler_reconciles_fill_with_real_price(tmp_path: Path) -> None:
    engine, app = _build_engine(tmp_path)
    reconciler = TradeReconciler(engine=engine)

    reconciler.mark_closing(
        symbol="MES JUN26",
        signal="BUY",
        entry_price=5000.0,
        detected_exit_price=5002.0,
        quantity=2,
        expected_pnl=20.0,
        reflection={"reason": "target hit"},
    )

    assert len(engine.pending_trade_reconciliations) == 1

    reconciler.ingest_fill_event(
        {
            "type": "fill",
            "instrument": "MES JUN26",
            "side": "SELL",
            "quantity": 2,
            "fillPrice": 5001.5,
            "commission": 1.25,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "fillId": "fill-123",
        }
    )

    assert engine.pending_trade_reconciliations == []
    assert len(app.pushes) == 1
    pushed = app.pushes[0]
    assert pushed["exit_price"] == 5001.5
    assert pushed["qty"] == 2
    assert round(float(pushed["pnl_dollars"]), 2) == 13.75
    assert pushed["reflection"]["reconciliation"]["broker_fill_id"] == "fill-123"
    assert pushed["reflection"]["reconciliation"]["status"] == "reconciled_fill"
    assert len(app.publishes) == 1
    assert len(app.thoughts) == 1


def test_trade_reconciler_timeout_uses_snapshot_when_no_fill(tmp_path: Path) -> None:
    engine, app = _build_engine(tmp_path)
    engine.config.use_real_fill_for_pnl = False
    engine.config.reconciliation_timeout_seconds = 0.0
    reconciler = TradeReconciler(engine=engine)

    reconciler.mark_closing(
        symbol="MES JUN26",
        signal="SELL",
        entry_price=5000.0,
        detected_exit_price=4997.5,
        quantity=1,
        expected_pnl=12.5,
        reflection={},
    )
    reconciler._flush_timeouts()

    assert engine.pending_trade_reconciliations == []
    assert len(app.pushes) == 1
    pushed = app.pushes[0]
    assert pushed["exit_price"] == 4997.5
    assert pushed["reflection"]["reconciliation"]["status"] == "timeout_snapshot"
