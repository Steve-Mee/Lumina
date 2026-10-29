"""D8: after sim_gate ok, run_tick_exec still cannot place. Research bridge can."""

from __future__ import annotations

import pytest

from lumina_core.order_gatekeeper.ungated_place_block import (
    UNGATED_PLACE_BLOCK_REASON,
    assert_validation_gate_or_block,
)
from lumina_core.research_bridge.sim_gate import bind_sim_gate
from tests.research_bridge.s3_helpers import bind_passing


@pytest.fixture(autouse=True)
def _unbind() -> None:
    bind_sim_gate(None)
    yield
    bind_sim_gate(None)


@pytest.mark.unit
def test_supervisor_blocked_research_allowed() -> None:
    bind_passing()
    blocked, reason = assert_validation_gate_or_block(
        "supervisor_tick_exec.run_tick_exec",
        order_side="BUY",
        live_position_qty=0,
        order_qty=1,
        source_agent="research_bridge",
    )
    assert blocked is False
    assert reason == UNGATED_PLACE_BLOCK_REASON
    allowed, gate_reason = assert_validation_gate_or_block(
        "ninjatrader.broker.submit_order",
        order_side="BUY",
        live_position_qty=0,
        order_qty=1,
        source_agent="research_bridge",
    )
    assert allowed is True
    assert gate_reason == "research_sim_gate_ok"
