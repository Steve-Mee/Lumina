"""Stage2 Participation Envelope — hard occupancy physics."""

from __future__ import annotations

import pytest

from lumina_core.birth.stage2_participation_envelope import (
    MODE_FORCE_FLAT,
    MODE_FORCE_HOLD,
    MODE_FORCE_OPEN,
    MODE_PASSTHROUGH,
    decide_stage2_participation,
    participation_telemetry,
)


@pytest.mark.unit
def test_disabled_passthrough() -> None:
    d = decide_stage2_participation(
        enabled=False,
        range_flat_ratio=0.96,
        range_total_signals=500,
        position=0,
        bars_in_position=0,
    )
    assert d.mode == MODE_PASSTHROUGH
    assert d.action_override is None


@pytest.mark.unit
def test_warmup_signals() -> None:
    d = decide_stage2_participation(
        enabled=True,
        range_flat_ratio=0.96,
        range_total_signals=10,
        position=0,
        bars_in_position=0,
        min_signals=50,
    )
    assert d.mode == MODE_PASSTHROUGH
    assert d.reason == "warmup_signals"


@pytest.mark.unit
def test_over_flat_force_open() -> None:
    d = decide_stage2_participation(
        enabled=True,
        range_flat_ratio=0.964,
        range_total_signals=200,
        position=0,
        bars_in_position=0,
        force_open_step=0,
        min_signals=50,
        stop_pct=0.0075,
        target_pct=0.015,
    )
    assert d.mode == MODE_FORCE_OPEN
    assert d.action_override is not None
    assert d.action_override[0] == 1.0  # long
    assert d.action_override[2] <= 0.01  # stop ≤1%
    assert d.suppress_flatten is True


@pytest.mark.unit
def test_over_flat_force_hold_until_dwell() -> None:
    d = decide_stage2_participation(
        enabled=True,
        range_flat_ratio=0.96,
        range_total_signals=200,
        position=1,
        bars_in_position=3,
        min_dwell_bars=8,
    )
    assert d.mode == MODE_FORCE_HOLD
    assert d.action_override is not None
    assert d.action_override[0] == 0.0  # hold action
    assert d.suppress_flatten is True


@pytest.mark.unit
def test_over_flat_after_dwell_passthrough_but_suppress_flatten() -> None:
    d = decide_stage2_participation(
        enabled=True,
        range_flat_ratio=0.96,
        range_total_signals=200,
        position=1,
        bars_in_position=10,
        min_dwell_bars=8,
    )
    assert d.mode == MODE_PASSTHROUGH
    assert d.suppress_flatten is True


@pytest.mark.unit
def test_under_flat_suppress_entry() -> None:
    d = decide_stage2_participation(
        enabled=True,
        range_flat_ratio=0.10,
        range_total_signals=200,
        position=0,
        bars_in_position=0,
    )
    assert d.mode == MODE_FORCE_FLAT
    assert d.action_override is not None
    assert d.action_override[0] == 0.0


@pytest.mark.unit
def test_hysteresis_no_force_flat_at_band_edge() -> None:
    """flat=0.29 with hyst=0.02 stays PASSTHROUGH (force only below 0.28)."""
    d = decide_stage2_participation(
        enabled=True,
        range_flat_ratio=0.29,
        range_total_signals=200,
        position=0,
        bars_in_position=0,
        hysteresis=0.02,
        band_lo=0.30,
        band_hi=0.70,
    )
    assert d.mode == MODE_PASSTHROUGH
    assert d.reason == "in_band"


@pytest.mark.unit
def test_hysteresis_force_flat_below_enter() -> None:
    d = decide_stage2_participation(
        enabled=True,
        range_flat_ratio=0.25,
        range_total_signals=200,
        position=0,
        bars_in_position=0,
        hysteresis=0.02,
    )
    assert d.mode == MODE_FORCE_FLAT


@pytest.mark.unit
def test_in_band_passthrough() -> None:
    d = decide_stage2_participation(
        enabled=True,
        range_flat_ratio=0.50,
        range_total_signals=200,
        position=0,
        bars_in_position=0,
    )
    assert d.mode == MODE_PASSTHROUGH
    assert d.action_override is None


@pytest.mark.unit
def test_telemetry_sums_overrides() -> None:
    t = participation_telemetry(
        {
            MODE_FORCE_OPEN: 10,
            MODE_FORCE_HOLD: 40,
            MODE_FORCE_FLAT: 2,
            MODE_PASSTHROUGH: 100,
        }
    )
    assert t["participation_overrides_total"] == 52
    assert t["participation_force_open"] == 10


@pytest.mark.unit
def test_stage_ssot_high_flat_force_open_even_with_low_local_signals() -> None:
    """Stage cumulative flat/signals (not per-chunk) must dominate envelope law."""
    # Local rollout just started (would be warmup if only local signals counted).
    d = decide_stage2_participation(
        enabled=True,
        range_flat_ratio=0.95,
        range_total_signals=70_000,  # stage+local SSOT already past warmup
        position=0,
        bars_in_position=0,
        min_signals=50,
    )
    assert d.mode == MODE_FORCE_OPEN
    assert d.suppress_flatten is True
