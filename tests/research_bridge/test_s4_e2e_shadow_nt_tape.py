"""E2e: NT-PIT tape → shadow fill → continuity meter → sim_gate (gap 5b)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from lumina_core.research_bridge.continuity_meter import (
    ContinuityMeterRefused,
    measure_continuity,
    measure_fixture_daily,
)
from lumina_core.research_bridge.sim_gate import evaluate
from lumina_research.validation.nt_tape import NtTapeMaterializer, closed_bars_from_rows, fixture_closed_mes_bars
from tests.research_bridge.helpers import make_runtime, sealed_candidate
from tests.research_bridge.s3_helpers import passing_context


@pytest.mark.unit
@pytest.mark.safety_gate
def test_shadow_pipeline_on_nt_tape_then_meter_opens_gate(tmp_path: Path) -> None:
    now = datetime(2025, 12, 31, 21, 0, tzinfo=timezone.utc)
    rows = fixture_closed_mes_bars(now=now)
    bars = closed_bars_from_rows(rows, now=now, purpose="gate")
    materializer = NtTapeMaterializer(bars)
    assert materializer.tape_kind == "nt_pit"
    _bus, authority, runtime, _alerts, observe = make_runtime(tmp_path, tape_kind="nt_pit", close=5000.0)
    intent = runtime.on_candidate(sealed_candidate(authority, instrument="MES", quantity=1.0))
    assert intent is not None
    assert runtime.issued_fills()
    assert observe.calls
    runtime.assert_no_broker_submit()

    meter = measure_fixture_daily(instrument="MES")
    assert meter.passed is True
    assert meter.bar_sha256
    ok, reason = evaluate(passing_context(meter=meter, instrument="MES"))
    assert ok is True
    assert reason == "research_sim_gate_ok"
    with pytest.raises(ContinuityMeterRefused):
        measure_continuity(bars, instrument="MES")
