"""D10: first miss retries once; second miss or t>10 min escalates; no infinite retry."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from lumina_core.agent_orchestration.event_bus import EventBus
from lumina_core.engine.live_position_manager import LivePositionManager
from lumina_core.risk.alarm_executor import AlarmExecutor
from tests.research_bridge.s3_helpers import RecordingSubmitter

T0 = datetime(2026, 10, 29, 12, 0, tzinfo=timezone.utc)


class Clock:
    def __init__(self) -> None:
        self.now = T0

    def __call__(self) -> datetime:
        return self.now


@pytest.mark.unit
def test_first_miss_retries_second_escalates_no_forever(tmp_path: Path) -> None:
    clock = Clock()
    positions = LivePositionManager(app=SimpleNamespace())
    positions.set_strategy_qty("hyp-a", 2)
    submitter = RecordingSubmitter(accept=False)
    exe = AlarmExecutor(
        bus=EventBus(),
        positions=positions,
        submitter=submitter,
        jsonl_path=tmp_path / "alarm.jsonl",
        clock=clock,
    )
    exe._on_deweight(SimpleNamespace(payload={"hypothesis_id": "hyp-a", "instrument": "MES"}))
    first = len(submitter.orders)
    assert first >= 1
    clock.now = T0 + timedelta(seconds=301)
    exe.tick(clock.now)
    assert exe.jobs[0].retried is True
    assert exe.jobs[0].miss_count == 1
    after_retry = len(submitter.orders)
    clock.now = T0 + timedelta(seconds=601)
    exe.tick(clock.now)
    assert exe.jobs[0].closed is True
    after_escalate = len(submitter.orders)
    clock.now = T0 + timedelta(seconds=1200)
    exe.tick(clock.now)
    exe.tick(clock.now)
    assert len(submitter.orders) == after_escalate
    assert after_retry >= first
    log = (tmp_path / "alarm.jsonl").read_text(encoding="utf-8")
    assert "alarm_executor.sla_miss" in log
