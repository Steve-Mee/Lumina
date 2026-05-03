from __future__ import annotations

import logging
import json
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any, cast

from lumina_core.engine import EngineConfig, TradeReconciler
from lumina_core.engine.lumina_engine import LuminaEngine


def _build_engine(tmp_path: Path, *, trade_mode: str = "real") -> tuple[LuminaEngine, SimpleNamespace]:
    cfg = EngineConfig(
        state_file=tmp_path / "state.json",
        thought_log=tmp_path / "thought_log.jsonl",
        bible_file=tmp_path / "bible.json",
        live_jsonl=tmp_path / "live.jsonl",
        trade_mode=trade_mode,
        reconcile_fills=True,
        reconciliation_method="websocket",
        reconciliation_timeout_seconds=15.0,
        trade_reconciler_audit_log=tmp_path / "trade_reconcile_audit.jsonl",
        trade_reconciler_status_file=tmp_path / "trade_reconcile_status.json",
    )
    engine = cast(Any, LuminaEngine)(config=cfg)
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
    reconciler = TradeReconciler(engine)

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
    published = app.publishes[0]
    assert published["broker_fill_id"] == "fill-123"
    assert published["commission"] == 1.25
    assert published["reconciliation_status"] == "reconciled_fill"
    assert len(app.thoughts) == 1


def test_trade_reconciler_aggregates_partial_fills(tmp_path: Path) -> None:
    engine, app = _build_engine(tmp_path)
    reconciler = TradeReconciler(engine)

    reconciler.mark_closing(
        symbol="MES JUN26",
        signal="BUY",
        entry_price=5000.0,
        detected_exit_price=5002.0,
        quantity=3,
        expected_pnl=30.0,
        reflection={"reason": "target hit"},
    )

    reconciler.ingest_fill_event(
        {
            "type": "fill",
            "instrument": "MES JUN26",
            "side": "SELL",
            "quantity": 1,
            "fillPrice": 5001.0,
            "commission": 0.5,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "fillId": "fill-part-1",
        }
    )
    assert len(app.pushes) == 0

    reconciler.ingest_fill_event(
        {
            "type": "fill",
            "instrument": "MES JUN26",
            "side": "SELL",
            "quantity": 2,
            "fillPrice": 5001.5,
            "commission": 0.75,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "fillId": "fill-part-2",
        }
    )

    assert engine.pending_trade_reconciliations == []
    assert len(app.pushes) == 1
    pushed = app.pushes[0]
    assert pushed["qty"] == 3
    assert round(float(pushed["exit_price"]), 4) == round((5001.0 * 1 + 5001.5 * 2) / 3, 4)
    assert round(float(pushed["commission"]), 2) == 1.25


def test_trade_reconciler_timeout_no_economic_ledger_without_broker_fill(tmp_path: Path) -> None:
    engine, app = _build_engine(tmp_path)
    engine.config.reconciliation_timeout_seconds = 0.0
    reconciler = TradeReconciler(engine)

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
    assert len(app.pushes) == 0
    assert len(app.publishes) == 0
    assert engine.trade_reconciler_status.get("last_reconciled_trade", {}).get("economic_ledger_applied") is False


def test_trade_reconciler_handles_out_of_order_partial_fills(tmp_path: Path) -> None:
    engine, app = _build_engine(tmp_path)
    reconciler = TradeReconciler(engine)

    detected_ts = datetime.now(timezone.utc)
    reconciler.mark_closing(
        symbol="MES JUN26",
        signal="BUY",
        entry_price=5000.0,
        detected_exit_price=5002.0,
        quantity=3,
        expected_pnl=30.0,
        reflection={"reason": "target hit"},
        detected_ts=detected_ts,
    )

    # First ingest later timestamp, then earlier timestamp to simulate out-of-order arrival.
    reconciler.ingest_fill_event(
        {
            "type": "fill",
            "instrument": "MES JUN26",
            "side": "SELL",
            "quantity": 2,
            "fillPrice": 5001.5,
            "commission": 0.75,
            "timestamp": (detected_ts.replace(microsecond=0)).isoformat(),
            "fillId": "fill-later",
        }
    )
    assert len(app.pushes) == 0

    reconciler.ingest_fill_event(
        {
            "type": "fill",
            "instrument": "MES JUN26",
            "side": "SELL",
            "quantity": 1,
            "fillPrice": 5001.0,
            "commission": 0.5,
            "timestamp": (detected_ts.replace(microsecond=0)).isoformat(),
            "fillId": "fill-earlier",
        }
    )

    assert engine.pending_trade_reconciliations == []
    assert len(app.pushes) == 1
    pushed = app.pushes[0]
    assert pushed["qty"] == 3
    assert round(float(pushed["exit_price"]), 4) == round((5001.0 * 1 + 5001.5 * 2) / 3, 4)


def test_trade_reconciler_ignores_duplicate_fill_replay(tmp_path: Path) -> None:
    engine, app = _build_engine(tmp_path)
    reconciler = TradeReconciler(engine)

    reconciler.mark_closing(
        symbol="MES JUN26",
        signal="BUY",
        entry_price=5000.0,
        detected_exit_price=5002.0,
        quantity=2,
        expected_pnl=20.0,
        reflection={},
    )

    event = {
        "type": "fill",
        "instrument": "MES JUN26",
        "side": "SELL",
        "quantity": 2,
        "fillPrice": 5001.5,
        "commission": 1.25,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "fillId": "fill-dup-1",
    }
    accepted_first = reconciler.ingest_fill_event(event)
    accepted_second = reconciler.ingest_fill_event(event)

    assert accepted_first is True
    assert accepted_second is False
    assert len(app.pushes) == 1
    assert app.pushes[0]["reflection"]["reconciliation"]["broker_fill_id"] == "fill-dup-1"


def test_trade_reconciler_starts_for_sim_real_guard_mode(tmp_path: Path, monkeypatch) -> None:
    engine, _app = _build_engine(tmp_path, trade_mode="sim_real_guard")
    reconciler = TradeReconciler(engine)

    called = {"websocket": 0}
    monkeypatch.setattr(
        TradeReconciler,
        "_run_websocket_loop",
        lambda self: called.__setitem__("websocket", called["websocket"] + 1),
    )

    reconciler.start()

    assert called["websocket"] == 1


def test_trade_reconciler_audit_contains_mode_and_account_hint(tmp_path: Path) -> None:
    engine, _app = _build_engine(tmp_path, trade_mode="sim_real_guard")
    reconciler = TradeReconciler(engine)
    audit_path = Path(engine.config.trade_reconciler_audit_log)

    reconciler._append_audit_event({"event": "unit_test"})

    lines = [line for line in audit_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) >= 1
    event = json.loads(lines[-1])
    assert event["event"] == "unit_test"
    assert event["mode"] == "sim_real_guard"
    assert event["account_mode_hint"] == "sim"
