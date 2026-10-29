"""NT-PIT continuity meter: no caller float, daily tape, planted shift on NT returns."""

from __future__ import annotations

from dataclasses import replace

import pytest

from lumina_core.research_bridge.continuity_meter import (
    FAR_MAX,
    POWER_MIN,
    PRODUCED_BY,
    TTD_FAST_MAX_DAYS,
    TTD_SLOW_MAX_DAYS,
    ContinuityMeterRefused,
    bar_sha256,
    daily_closed_bars,
    fixture_closed_mes_daily_bars,
    measure_continuity,
    measure_fixture_daily,
)
from lumina_core.research_bridge.sim_gate import evaluate
from lumina_research.validation.nt_tape import TapeRefused, closed_bars_from_rows, fixture_closed_mes_bars
from tests.research_bridge.s3_helpers import passing_context


@pytest.mark.unit
@pytest.mark.safety_gate
def test_fixture_daily_meter_passes_floors() -> None:
    report = measure_fixture_daily(instrument="MES")
    assert report.produced_by == PRODUCED_BY
    assert report.tape_kind == "nt_pit"
    assert report.passed is True
    assert report.reason == "ok"
    assert 0.0 <= report.far <= FAR_MAX
    assert 0.0 < report.ttd_fast_days <= TTD_FAST_MAX_DAYS
    assert 0.0 < report.ttd_slow_days <= TTD_SLOW_MAX_DAYS
    assert report.ttd_slow_days >= report.ttd_fast_days
    assert report.power >= POWER_MIN
    assert len(report.bar_sha256) == 64


@pytest.mark.unit
@pytest.mark.safety_gate
def test_intraday_tape_is_not_ttd_evidence() -> None:
    from datetime import datetime, timezone

    now = datetime(2025, 12, 31, 21, 0, tzinfo=timezone.utc)
    bars = closed_bars_from_rows(fixture_closed_mes_bars(now=now), now=now, purpose="gate")
    with pytest.raises(ContinuityMeterRefused, match="ttd_requires_daily_tape"):
        measure_continuity(bars, instrument="MES")


@pytest.mark.unit
@pytest.mark.safety_gate
def test_meter_refuses_short_and_non_closed() -> None:
    with pytest.raises(ContinuityMeterRefused):
        measure_continuity([], instrument="MES")
    with pytest.raises(ContinuityMeterRefused):
        measure_continuity("nope")  # type: ignore[arg-type]
    with pytest.raises((ContinuityMeterRefused, TapeRefused)):
        fixture_closed_mes_daily_bars(n=10)


@pytest.mark.unit
@pytest.mark.safety_gate
def test_sim_gate_rejects_caller_float_and_unbound_report() -> None:
    ok, reason = evaluate(passing_context(meter=None))
    assert ok is False
    assert reason == "continuity_unmeasured"
    ok, reason = evaluate(passing_context(meter=0.02))
    assert ok is False
    assert reason == "continuity_unmeasured"
    report = measure_fixture_daily()
    fake = replace(report, produced_by="hand_built")
    ok, reason = evaluate(passing_context(meter=fake))
    assert ok is False
    assert reason == "continuity_unmeasured"
    fake_tape = replace(report, tape_kind="synthetic")
    ok, reason = evaluate(passing_context(meter=fake_tape))
    assert ok is False
    assert reason == "continuity_not_nt_pit"
    high = replace(report, far=0.11, passed=False, reason="far_above_floor")
    ok, reason = evaluate(passing_context(meter=high))
    assert ok is False
    assert reason == "far_above_floor"


@pytest.mark.unit
def test_bar_hash_binds_tape() -> None:
    bars = daily_closed_bars()
    digest = bar_sha256(bars)
    assert digest == bar_sha256(bars)
    assert digest != bar_sha256(bars[:-1])
