"""Prolonged disconnect flatten via Risk Core; broker is SoT (ADR-0064)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from lumina_core.agent_orchestration.event_bus import EventBus
from lumina_core.engine.live_position_manager import LivePositionManager
from lumina_core.research_bridge.alerts import RecordingAlertSink
from lumina_core.risk.alarm_executor import AlarmExecutor
from lumina_core.risk.prolonged_disconnect import (
    FLATTEN_GRACE_HARD_MS,
    PROLONGED_DISCONNECT_MAX_MS,
    PROLONGED_DISCONNECT_MIN_MS,
    PROLONGED_DISCONNECT_MS,
    pin_flatten_grace_ms,
    registered_prolonged_disconnect_ms,
    should_flatten_unprotected,
)
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


@pytest.mark.unit
@pytest.mark.safety_gate
def test_flatten_grace_is_hard_five_seconds() -> None:
    assert FLATTEN_GRACE_HARD_MS == 5000
    assert pin_flatten_grace_ms(0) == 5000
    assert pin_flatten_grace_ms(15000) == 5000
    assert pin_flatten_grace_ms(30000) == 5000
    assert pin_flatten_grace_ms(60000) == 5000
    yaml = Path("config.yaml").read_text(encoding="utf-8")
    assert "flatten_grace_ms: 5000" in yaml
    assert "flatten_grace_ms: 30000" not in yaml
    assert "prolonged_disconnect_ms: 30000" in yaml


@pytest.mark.unit
@pytest.mark.safety_gate
def test_prolonged_threshold_is_registered_30s() -> None:
    assert PROLONGED_DISCONNECT_MS == 30000
    assert PROLONGED_DISCONNECT_MIN_MS == 30000
    assert PROLONGED_DISCONNECT_MAX_MS == 60000
    assert registered_prolonged_disconnect_ms(45_000) == 30000
    assert should_flatten_unprotected(disconnected_ms=29999, has_confirmed_server_stop=False) is False
    assert should_flatten_unprotected(disconnected_ms=30000, has_confirmed_server_stop=False) is True
    assert should_flatten_unprotected(disconnected_ms=30000, has_confirmed_server_stop=True) is False
    assert should_flatten_unprotected(disconnected_ms=30000, has_confirmed_server_stop=None) is True
    assert should_flatten_unprotected(disconnected_ms="bad", has_confirmed_server_stop=False) is True


@pytest.mark.unit
@pytest.mark.safety_gate
def test_maybe_flatten_respects_threshold_and_confirmed_stop(tmp_path: Path) -> None:
    positions = LivePositionManager(app=SimpleNamespace())
    positions.set_strategy_qty("hyp-a", 2)
    submitter = RecordingSubmitter()
    exe = AlarmExecutor(
        bus=EventBus(),
        positions=positions,
        submitter=submitter,
        jsonl_path=tmp_path / "alarm.jsonl",
        clock=lambda: T0,
    )
    n = exe.maybe_flatten_after_disconnect(instrument="MES", disconnected_ms=29999)
    assert n == 0
    assert exe.prolonged_flattens == 0
    assert positions.strategy_qty("hyp-a") == 2
    n = exe.maybe_flatten_after_disconnect(
        instrument="MES",
        disconnected_ms=30000,
        confirmed_server_stop_by_strategy={"hyp-a": True},
    )
    assert n == 0
    assert positions.strategy_qty("hyp-a") == 2
    n = exe.maybe_flatten_after_disconnect(instrument="MES", disconnected_ms=30000)
    assert n == 1
    assert positions.strategy_qty("hyp-a") == 0
    assert submitter.orders[-1].quantity == 2
    assert exe.maybe_flatten_after_disconnect(instrument="MES", disconnected_ms=30000) == 0
