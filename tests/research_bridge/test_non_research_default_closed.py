"""Manual/legacy place_order stays denied unless a logged ADR+human release exists."""

from __future__ import annotations

import pytest

from lumina_core.order_gatekeeper.ungated_place_block import (
    UNGATED_PLACE_BLOCK_REASON,
    assert_validation_gate_or_block,
)
from lumina_core.research_bridge.sim_gate import (
    LoggedHumanRelease,
    bind_logged_human_release,
    bind_sim_gate,
)
from tests.research_bridge.s3_helpers import bind_passing


@pytest.fixture(autouse=True)
def _unbind() -> None:
    bind_sim_gate(None)
    bind_logged_human_release(None)
    yield
    bind_sim_gate(None)
    bind_logged_human_release(None)


@pytest.mark.unit
def test_manual_denied_even_when_sim_gate_ok() -> None:
    bind_passing()
    allowed, reason = assert_validation_gate_or_block(
        "operations_service_orders.place_order",
        order_side="BUY",
        live_position_qty=0,
        order_qty=1,
        source_agent="operations_service",
    )
    assert allowed is False
    assert reason == UNGATED_PLACE_BLOCK_REASON


@pytest.mark.unit
def test_logged_release_still_not_supervisor() -> None:
    bind_passing()
    bind_logged_human_release(
        LoggedHumanRelease(adr_path="docs/adr/0063-sim-orders-gated.md", approved_by="steve", purpose="manual_place")
    )
    allowed, reason = assert_validation_gate_or_block(
        "operations_service_orders.place_order",
        order_side="BUY",
        live_position_qty=0,
        order_qty=1,
        source_agent="operations_service",
    )
    assert allowed is True
    assert reason == "non_research_logged_release"
    blocked, freeze = assert_validation_gate_or_block(
        "supervisor_tick_exec.run_tick_exec",
        order_side="BUY",
        live_position_qty=0,
        order_qty=1,
    )
    assert blocked is False
    assert freeze == UNGATED_PLACE_BLOCK_REASON
