"""SAFE_MODE / disconnect: no new research places; reconcile on reconnect."""

from __future__ import annotations

from pathlib import Path

import pytest

from lumina_core.agent_orchestration.event_bus import EventBus
from lumina_core.engine.live_position_manager import LivePositionManager
from lumina_core.research_bridge.fill_index import FillIndex
from lumina_core.research_bridge.market_health import unhealthy_market
from lumina_core.research_bridge.sim_gate import bind_sim_gate
from lumina_core.research_bridge.sim_runtime import SimRuntime
from lumina_core.risk.alarm_executor import AlarmExecutor
from lumina_research.agents.provenance import ProvenanceAuthority
from tests.research_bridge.helpers import sealed_candidate
from tests.research_bridge.s3_helpers import RecordingSubmitter, fake_engine, passing_context


@pytest.fixture(autouse=True)
def _unbind() -> None:
    bind_sim_gate(None)
    yield
    bind_sim_gate(None)


@pytest.mark.unit
def test_disconnect_blocks_new_research_places(tmp_path: Path) -> None:
    ctx = passing_context(market=False)
    bind_sim_gate(ctx)
    submitter = RecordingSubmitter()
    runtime = SimRuntime(
        bus=EventBus(),
        authority=ProvenanceAuthority(),
        jsonl_path=tmp_path / "s3.jsonl",
        market=unhealthy_market(),
        fill_index=FillIndex(),
        gate_ctx=ctx,
        engine=fake_engine(),
        submitter=submitter,
        pre_trade_gate=lambda *args, **kwargs: (True, "ok"),
    )
    runtime.on_candidate(sealed_candidate(runtime._authority))
    assert submitter.orders == []


@pytest.mark.unit
def test_reconcile_on_reconnect(tmp_path: Path) -> None:
    from types import SimpleNamespace

    exe = AlarmExecutor(
        bus=EventBus(),
        positions=LivePositionManager(app=SimpleNamespace()),
        submitter=RecordingSubmitter(),
        jsonl_path=tmp_path / "alarm.jsonl",
    )
    exe.reconcile_on_reconnect()
    assert exe.reconciles == 1
    log = (tmp_path / "alarm.jsonl").read_text(encoding="utf-8")
    assert "alarm_executor.reconcile" in log
