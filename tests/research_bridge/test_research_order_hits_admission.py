"""Research order invokes admission; a reject anywhere means no Fabric submit."""

from __future__ import annotations

from pathlib import Path

import pytest

from lumina_core.agent_orchestration.event_bus import EventBus
from lumina_core.research_bridge.fill_index import FillIndex
from lumina_core.research_bridge.market_health import healthy_closed_bar
from lumina_core.research_bridge.sim_gate import bind_sim_gate
from lumina_core.research_bridge.sim_runtime import SimRuntime
from lumina_research.agents.provenance import ProvenanceAuthority
from tests.research_bridge.helpers import sealed_candidate
from tests.research_bridge.s3_helpers import RecordingSubmitter, bind_passing, fake_engine, passing_context


@pytest.fixture(autouse=True)
def _unbind() -> None:
    bind_sim_gate(None)
    yield
    bind_sim_gate(None)


@pytest.mark.unit
def test_admission_reject_no_fabric(tmp_path: Path) -> None:
    ctx = passing_context()
    bind_sim_gate(ctx)
    calls: list[str] = []

    def gate(engine: object, **kwargs: object) -> tuple[bool, str]:
        del engine, kwargs
        calls.append("gate")
        return False, "constitution_blocked"

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
        pre_trade_gate=gate,
    )
    runtime.on_candidate(sealed_candidate(runtime._authority, instrument="MES"))
    assert calls == ["gate"]
    assert submitter.orders == []
    assert runtime.broker_submit_count() == 0


@pytest.mark.unit
def test_admission_ok_submits(tmp_path: Path) -> None:
    ctx = bind_passing()
    calls: list[str] = []

    def gate(engine: object, **kwargs: object) -> tuple[bool, str]:
        del engine, kwargs
        calls.append("gate")
        return True, "ok"

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
        pre_trade_gate=gate,
    )
    result = runtime.on_candidate(sealed_candidate(runtime._authority, instrument="MES"))
    assert calls == ["gate"]
    assert result is not None
    assert result.accepted is True
    assert len(submitter.orders) == 1
    assert submitter.orders[0].symbol == "MES"
    assert submitter.orders[0].metadata.get("mode_context") == "sim_real_guard"
