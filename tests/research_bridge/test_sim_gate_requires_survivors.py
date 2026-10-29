"""S3: 0/1 survivor or clones/synthetics cannot open place_order."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from lumina_core.agent_orchestration.event_bus import EventBus
from lumina_core.order_gatekeeper.ungated_place_block import assert_validation_gate_or_block
from lumina_core.research_bridge.fill_index import FillIndex
from lumina_core.research_bridge.market_health import healthy_closed_bar
from lumina_core.research_bridge.sim_gate import bind_sim_gate, evaluate
from lumina_core.research_bridge.sim_runtime import SimRuntime
from lumina_research.agents.provenance import ProvenanceAuthority
from tests.research_bridge.helpers import sealed_candidate
from tests.research_bridge.s3_helpers import (
    RecordingSubmitter,
    bind_passing,
    fake_engine,
    passing_context,
    survivor,
)


@pytest.fixture(autouse=True)
def _unbind() -> None:
    bind_sim_gate(None)
    yield
    bind_sim_gate(None)


@pytest.mark.unit
def test_zero_or_one_survivor_blocks(tmp_path: Path) -> None:
    del tmp_path
    ok, reason = evaluate(passing_context(survivors=()))
    assert ok is False
    assert reason == "survivors_insufficient"
    ok, reason = evaluate(passing_context(survivors=(survivor(tag="only", family="trend"),)))
    assert ok is False
    assert reason == "survivors_insufficient"


@pytest.mark.unit
def test_two_d11_independent_nt_pit_pass() -> None:
    ctx = passing_context()
    ok, reason = evaluate(ctx)
    assert ok is True
    assert reason == "research_sim_gate_ok"


@pytest.mark.unit
def test_same_config_clones_not_independent() -> None:
    left = survivor(tag="a", family="trend")
    right = replace(survivor(tag="a2", family="meanrev"), config_id=left.config_id)
    ok, reason = evaluate(passing_context(survivors=(left, right)))
    assert ok is False
    assert "config" in reason or "independent" in reason or "insufficient" in reason


@pytest.mark.unit
def test_two_synthetic_gate_passes_still_refuse() -> None:
    rows = (
        survivor(tag="s1", family="trend", tape_kind="synthetic"),
        survivor(tag="s2", family="meanrev", tape_kind="synthetic"),
    )
    ok, reason = evaluate(passing_context(survivors=rows))
    assert ok is False
    assert reason in {"survivors_not_nt_pit", "survivors_insufficient"}


@pytest.mark.unit
def test_place_order_not_called_without_survivors(tmp_path: Path) -> None:
    ctx = passing_context(survivors=())
    bind_sim_gate(ctx)
    submitter = RecordingSubmitter()
    bus = EventBus()
    runtime = SimRuntime(
        bus=bus,
        authority=ProvenanceAuthority(),
        jsonl_path=tmp_path / "s3.jsonl",
        market=healthy_closed_bar(close=5000.0),
        fill_index=FillIndex(),
        gate_ctx=ctx,
        engine=fake_engine(),
        submitter=submitter,
    )
    candidate = sealed_candidate(runtime._authority, instrument="MES")
    result = runtime.on_candidate(candidate)
    assert result is None
    assert submitter.orders == []
    allowed, _reason = assert_validation_gate_or_block(
        "ninjatrader.broker.submit_order",
        order_side="BUY",
        source_agent="research_bridge",
        live_position_qty=0,
        order_qty=1,
    )
    assert allowed is False


@pytest.mark.unit
def test_two_survivors_allow_research_place() -> None:
    bind_passing()
    allowed, reason = assert_validation_gate_or_block(
        "ninjatrader.broker.submit_order",
        order_side="BUY",
        source_agent="research_bridge",
        live_position_qty=0,
        order_qty=1,
    )
    assert allowed is True
    assert reason == "research_sim_gate_ok"
