"""D9: retired / disable / critical / hard DD / disconnect → flatten that strategy."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from lumina_core.agent_orchestration.event_bus import EventBus
from lumina_core.engine.live_position_manager import LivePositionManager
from lumina_core.risk.alarm_executor import AlarmExecutor
from tests.research_bridge.s3_helpers import RecordingSubmitter


@pytest.mark.unit
def test_retire_flattens_strategy_only(tmp_path: Path) -> None:
    positions = LivePositionManager(app=SimpleNamespace())
    positions.set_strategy_qty("hyp-a", 2)
    positions.set_strategy_qty("hyp-b", 3)
    submitter = RecordingSubmitter()
    exe = AlarmExecutor(
        bus=EventBus(),
        positions=positions,
        submitter=submitter,
        jsonl_path=tmp_path / "alarm.jsonl",
        clock=lambda: datetime(2026, 10, 29, 12, 0, tzinfo=timezone.utc),
    )
    exe._on_retire(SimpleNamespace(payload={"hypothesis_id": "hyp-a", "instrument": "MES"}))
    assert submitter.orders[0].quantity == 2
    assert exe.positions.strategy_qty("hyp-a") == 0
    assert exe.positions.strategy_qty("hyp-b") == 3


@pytest.mark.unit
def test_critical_guardian_flattens(tmp_path: Path) -> None:
    positions = LivePositionManager(app=SimpleNamespace())
    positions.set_strategy_qty("sig-1", 2)
    submitter = RecordingSubmitter()
    exe = AlarmExecutor(
        bus=EventBus(),
        positions=positions,
        submitter=submitter,
        jsonl_path=tmp_path / "alarm.jsonl",
        clock=lambda: datetime(2026, 10, 29, 12, 0, tzinfo=timezone.utc),
    )
    exe._on_guardian(
        SimpleNamespace(
            payload={"signal_id": "sig-1", "hypothesis_id": "sig-1", "severity": "critical", "instrument": "MNQ"}
        )
    )
    assert submitter.orders[0].quantity == 2
    assert exe.positions.strategy_qty("sig-1") == 0
