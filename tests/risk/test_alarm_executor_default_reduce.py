"""D9: deweight or suspend with open qty 2 → reduce-only qty 1. Research not in submit stack."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from lumina_core.agent_orchestration.event_bus import EventBus
from lumina_core.engine.live_position_manager import LivePositionManager
from lumina_core.risk.alarm_executor import AlarmExecutor
from tests.research_bridge.s3_helpers import RecordingSubmitter


def _executor(tmp_path: Path, submitter: RecordingSubmitter, qty: int = 2) -> AlarmExecutor:
    positions = LivePositionManager(app=SimpleNamespace())
    positions.set_strategy_qty("hyp-a", qty)
    exe = AlarmExecutor(
        bus=EventBus(),
        positions=positions,
        submitter=submitter,
        jsonl_path=tmp_path / "alarm.jsonl",
        clock=lambda: datetime(2026, 10, 29, 12, 0, tzinfo=timezone.utc),
    )
    return exe


@pytest.mark.unit
@pytest.mark.parametrize("stage_method", ["_on_deweight", "_on_suspend"])
def test_deweight_or_suspend_reduces_half(tmp_path: Path, stage_method: str) -> None:
    submitter = RecordingSubmitter()
    exe = _executor(tmp_path, submitter)
    event = SimpleNamespace(payload={"hypothesis_id": "hyp-a", "signal_id": "hyp-a", "instrument": "MES"})
    getattr(exe, stage_method)(event)
    assert len(submitter.orders) == 1
    order = submitter.orders[0]
    assert order.quantity == 1
    assert order.metadata.get("reduce_only") is True
    assert order.side == "SELL"
    stack = "\n".join(submitter.stack_at_submit)
    assert "lumina_research" not in stack
    assert exe.positions.strategy_qty("hyp-a") == 1
