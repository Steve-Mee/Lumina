"""D8: supervisor confluence cannot place and cannot mint a research order."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from lumina_core.engine.supervisor_tick_ctx import SupervisorTickCtx
from lumina_core.engine.supervisor_tick_exec import run_tick_exec
from lumina_core.order_gatekeeper.ungated_place_block import UNGATED_PLACE_BLOCK_REASON

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.unit
def test_supervisor_cannot_place_on_confluence_buy_or_sell() -> None:
    for signal in ("BUY", "SELL"):
        place = MagicMock(return_value=True)
        app = SimpleNamespace(
            calculate_adaptive_risk_and_qty=lambda *_a, **_k: 3,
            sim_position_qty=0,
            place_order=place,
            open_pnl=0.0,
            account_equity=50.0,
            account_balance=50.0,
            logger=MagicMock(),
        )
        sm = SimpleNamespace(app=app, engine=None, valuation_engine=MagicMock(), _logger=MagicMock())
        ctx = SupervisorTickCtx(
            price=5000.0,
            dream_snapshot={"confluence_score": 1.0, "regime": "TREND", "stop": 4990.0, "target": 5010.0},
            now=datetime(2026, 10, 28, tzinfo=timezone.utc),
            signal=signal,
            trade_mode="sim",
            min_confluence=0.1,
        )
        run_tick_exec(sm, ctx)
        place.assert_not_called()
        assert ctx.signal in {signal, "HOLD"}


@pytest.mark.unit
def test_supervisor_cannot_turn_ctx_signal_into_research_order() -> None:
    source = (ROOT / "lumina_core" / "engine" / "supervisor_tick_exec.py").read_text(encoding="utf-8")
    assert "research.execution" not in source
    assert "SignalIntent" not in source
    assert "ResearchExecutionOrderIntent" not in source
    assert UNGATED_PLACE_BLOCK_REASON in source or "assert_validation_gate_or_block" in source
