"""Prolonged disconnect flatten via Risk Core; broker is SoT (ADR-0064 Proposed)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from lumina_core.agent_orchestration.event_bus import EventBus
from lumina_core.engine.live_position_manager import LivePositionManager
from lumina_core.research_bridge.alerts import RecordingAlertSink
from lumina_core.risk.alarm_executor import AlarmExecutor
from tests.research_bridge.s3_helpers import RecordingSubmitter

T0 = datetime(2026, 10, 29, 15, 39, tzinfo=timezone.utc)


@pytest.mark.unit
@pytest.mark.safety_gate
def test_prolonged_disconnect_flattens_open_strategy(tmp_path: Path) -> None:
    positions = LivePositionManager(app=SimpleNamespace())
    positions.set_strategy_qty("hyp-a", 2)
    submitter = RecordingSubmitter()
    sink = RecordingAlertSink()
    exe = AlarmExecutor(
        bus=EventBus(),
        positions=positions,
        submitter=submitter,
        jsonl_path=tmp_path / "alarm.jsonl",
        clock=lambda: T0,
        alert_sink=sink,
    )
    exe.flatten_on_prolonged_disconnect(instrument="MES")
    assert exe.reconciles == 1
    assert exe.prolonged_flattens >= 1
    assert positions.strategy_qty("hyp-a") == 0
    assert submitter.orders
    assert submitter.orders[-1].quantity == 2
    assert any(item["code"] == "prolonged_disconnect_flatten" for item in sink.records)


@pytest.mark.unit
def test_prolonged_disconnect_noop_when_flat(tmp_path: Path) -> None:
    positions = LivePositionManager(app=SimpleNamespace())
    submitter = RecordingSubmitter()
    exe = AlarmExecutor(
        bus=EventBus(),
        positions=positions,
        submitter=submitter,
        jsonl_path=tmp_path / "alarm.jsonl",
        clock=lambda: T0,
    )
    exe.flatten_on_prolonged_disconnect()
    assert exe.reconciles == 1
    assert exe.prolonged_flattens == 0
    assert submitter.orders == []


@pytest.mark.unit
def test_prolonged_disconnect_uses_broker_sot_qty(tmp_path: Path) -> None:
    positions = LivePositionManager(app=SimpleNamespace())
    positions._pos.live_position_qty = 1
    submitter = RecordingSubmitter()
    exe = AlarmExecutor(
        bus=EventBus(),
        positions=positions,
        submitter=submitter,
        jsonl_path=tmp_path / "alarm.jsonl",
        clock=lambda: T0,
    )
    exe.flatten_on_prolonged_disconnect(instrument="MES")
    assert exe.prolonged_flattens >= 1
    assert submitter.orders
    assert submitter.orders[-1].quantity == 1
