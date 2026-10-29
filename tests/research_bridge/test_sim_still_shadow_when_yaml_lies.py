"""Yaml sim is not enough. Missing NT-PIT survivors keep Fabric closed. D1/D8 hold."""

from __future__ import annotations

from pathlib import Path

import pytest

from lumina_core.agent_orchestration.event_bus import EventBus
from lumina_core.order_gatekeeper.ungated_place_block import (
    UNGATED_PLACE_BLOCK_REASON,
    assert_validation_gate_or_block,
)
from lumina_core.research_bridge.fill_index import FillIndex
from lumina_core.research_bridge.market_health import healthy_closed_bar
from lumina_core.research_bridge.sim_gate import bind_sim_gate
from lumina_core.research_bridge.sim_runtime import SimRuntime
from lumina_research.agents.provenance import ProvenanceAuthority
from tests.research_bridge.helpers import sealed_candidate
from tests.research_bridge.s3_helpers import RecordingSubmitter, fake_engine, passing_context, survivor


@pytest.fixture(autouse=True)
def _unbind() -> None:
    bind_sim_gate(None)
    yield
    bind_sim_gate(None)


@pytest.mark.unit
def test_yaml_sim_synthetic_only_does_not_call_fabric(tmp_path: Path) -> None:
    ctx = passing_context(
        boot="shadow",
        yaml_now="sim",
        survivors=(
            survivor(tag="s1", family="trend", tape_kind="synthetic"),
            survivor(tag="s2", family="meanrev", tape_kind="synthetic"),
        ),
    )
    bind_sim_gate(ctx)
    submitter = RecordingSubmitter()
    runtime = SimRuntime(
        bus=EventBus(),
        authority=ProvenanceAuthority(),
        jsonl_path=tmp_path / "s3.jsonl",
        market=healthy_closed_bar(close=5000.0),
        fill_index=FillIndex(),
        gate_ctx=ctx,
        engine=fake_engine(),
        submitter=submitter,
    )
    runtime.on_candidate(sealed_candidate(runtime._authority))
    assert submitter.orders == []
    allowed, reason = assert_validation_gate_or_block(
        "supervisor_tick_exec.run_tick_exec",
        order_side="BUY",
        live_position_qty=0,
        order_qty=1,
        source_agent="research_bridge",
    )
    assert allowed is False
    assert reason == UNGATED_PLACE_BLOCK_REASON
