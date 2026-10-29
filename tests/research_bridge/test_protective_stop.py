"""Protective stop: refuse unprotected sim_real_guard entries; companion STOP."""

from __future__ import annotations

from pathlib import Path

import pytest

from lumina_core.agent_orchestration.event_bus import EventBus
from lumina_core.broker.broker_bridge.schemas import Order
from lumina_core.research_bridge.fill_index import FillIndex
from lumina_core.research_bridge.market_health import healthy_closed_bar
from lumina_core.research_bridge.protective_stop import (
    UNPROTECTED_ENTRY,
    companion_stop_order,
    require_protective_stop,
)
from lumina_core.research_bridge.sim_gate import bind_sim_gate
from lumina_core.research_bridge.sim_runtime import SimRuntime
from lumina_research.agents.provenance import ProvenanceAuthority
from tests.research_bridge.helpers import sealed_candidate
from tests.research_bridge.s3_helpers import RecordingSubmitter, fake_engine, passing_context


@pytest.mark.unit
@pytest.mark.safety_gate
def test_unprotected_sim_real_guard_refused() -> None:
    order = Order(
        symbol="MES",
        side="BUY",
        quantity=1,
        order_type="MARKET",
        metadata={"mode_context": "sim_real_guard"},
    )
    ok, reason = require_protective_stop(order)
    assert ok is False
    assert reason == UNPROTECTED_ENTRY


@pytest.mark.unit
def test_reduce_only_may_omit_stop() -> None:
    order = Order(
        symbol="MES",
        side="SELL",
        quantity=1,
        order_type="MARKET",
        metadata={"mode_context": "sim_real_guard", "reduce_only": True},
    )
    ok, reason = require_protective_stop(order)
    assert ok is True


@pytest.mark.unit
def test_companion_stop_is_protected() -> None:
    entry = Order(
        symbol="MES",
        side="BUY",
        quantity=1,
        order_type="MARKET",
        stop_loss=4950.0,
        metadata={"mode_context": "sim_real_guard", "stop_price": 4950.0, "strategy_id": "h"},
    )
    stop = companion_stop_order(entry, client_order_id="c-stop")
    assert stop.order_type == "STOP"
    assert stop.side == "SELL"
    assert stop.metadata.get("protected") is True
    assert stop.metadata.get("reduce_only") is True
    assert stop.stop_loss == pytest.approx(4950.0)


@pytest.mark.unit
@pytest.mark.safety_gate
def test_sim_runtime_submits_companion_stop(tmp_path: Path) -> None:
    ctx = passing_context()
    bind_sim_gate(ctx)
    submitter = RecordingSubmitter()
    runtime = SimRuntime(
        bus=EventBus(),
        authority=ProvenanceAuthority(),
        jsonl_path=tmp_path / "s4.jsonl",
        market=healthy_closed_bar(close=5000.0),
        fill_index=FillIndex(),
        gate_ctx=ctx,
        engine=fake_engine(),
        submitter=submitter,
        pre_trade_gate=lambda *args, **kwargs: (True, "ok"),
    )
    result = runtime.on_candidate(sealed_candidate(runtime._authority, instrument="MES"))
    assert result is not None
    assert result.accepted is True
    assert len(submitter.orders) == 2
    assert submitter.orders[0].stop_loss > 0.0
    assert submitter.orders[1].order_type == "STOP"
    assert submitter.orders[1].metadata.get("protected") is True
    bind_sim_gate(None)


@pytest.mark.unit
@pytest.mark.safety_gate
def test_companion_stop_reject_is_fail_closed(tmp_path: Path) -> None:
    ctx = passing_context()
    bind_sim_gate(ctx)

    class _RejectStop(RecordingSubmitter):
        def submit_order(self, order: Order):
            if str(order.order_type).upper() == "STOP":
                self.accept = False
            return super().submit_order(order)

    submitter = _RejectStop()
    runtime = SimRuntime(
        bus=EventBus(),
        authority=ProvenanceAuthority(),
        jsonl_path=tmp_path / "s4-deny-stop.jsonl",
        market=healthy_closed_bar(close=5000.0),
        fill_index=FillIndex(),
        gate_ctx=ctx,
        engine=fake_engine(),
        submitter=submitter,
        pre_trade_gate=lambda *args, **kwargs: (True, "ok"),
    )
    result = runtime.on_candidate(sealed_candidate(runtime._authority, instrument="MES"))
    assert result is None
    assert len(runtime._fill_index) == 0
    bind_sim_gate(None)
