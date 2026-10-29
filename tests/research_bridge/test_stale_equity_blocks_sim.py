"""Stale snapshot blocks new research orders; reduce-only still allowed."""

from __future__ import annotations

import pytest

from lumina_core.order_gatekeeper.ungated_place_block import assert_validation_gate_or_block
from lumina_core.research_bridge.sim_gate import bind_sim_gate, evaluate
from tests.research_bridge.s3_helpers import passing_context


@pytest.fixture(autouse=True)
def _unbind() -> None:
    bind_sim_gate(None)
    yield
    bind_sim_gate(None)


@pytest.mark.unit
def test_stale_blocks_new_allows_reduce() -> None:
    new_ctx = passing_context(stale=True, reduce_only=False)
    ok, reason = evaluate(new_ctx)
    assert ok is False
    assert reason == "equity_snapshot_stale"
    reduce_ctx = passing_context(stale=True, reduce_only=True)
    ok, reason = evaluate(reduce_ctx)
    assert ok is True
    allowed, allow_reason = assert_validation_gate_or_block(
        "ninjatrader.broker.submit_order",
        reduce_only=True,
        order_side="SELL",
        live_position_qty=2,
        order_qty=1,
    )
    assert allowed is True
    assert allow_reason == "reduce_only_allowed"
