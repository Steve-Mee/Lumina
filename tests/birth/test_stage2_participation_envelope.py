"""Stage2 Participation Envelope — hard occupancy physics."""

from __future__ import annotations

import pytest

from lumina_core.birth.stage2_participation_envelope import (
    MODE_FORCE_EXIT,
    MODE_FORCE_FLAT,
    MODE_FORCE_HOLD,
    MODE_FORCE_OPEN,
    MODE_PASSTHROUGH,
    decide_stage2_participation,
    force_open_stop_from_atr,
    occupancy_control_flat,
    occupancy_control_over,
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
        stop_pct=0.00064,
        target_pct=0.00101,
    )
    assert d.mode == MODE_FORCE_OPEN
    assert d.action_override is not None
    assert d.action_override[0] == 1.0  # long
    assert d.action_override[2] == pytest.approx(0.00064)  # micro geometry preserved
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
    """Low flat = over-trading: FORCE_FLAT is correct (raises empty ratio into band)."""
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
    assert "under_flat" in d.reason


@pytest.mark.unit
def test_flat_028_dead_zone_now_force_flat() -> None:
    """Live forensics: flat 28% must FORCE_FLAT (enter at band_lo 0.30, no 28–30% dead zone)."""
    d = decide_stage2_participation(
        enabled=True,
        range_flat_ratio=0.28,
        range_total_signals=500,
        position=0,
        bars_in_position=0,
        hysteresis=0.02,
        band_lo=0.30,
        band_hi=0.70,
    )
    assert d.mode == MODE_FORCE_FLAT
    assert "under_flat" in d.reason


@pytest.mark.unit
def test_flat_029_under_band_suppress() -> None:
    """flat=0.29 < band_lo=0.30 → suppress (asymmetric enter at pad)."""
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
    assert d.mode == MODE_FORCE_FLAT


@pytest.mark.unit
def test_release_hysteresis_suppress_until_032() -> None:
    """After under-band, release only above band_lo+0.02 (sticky suppress at 0.31)."""
    d = decide_stage2_participation(
        enabled=True,
        range_flat_ratio=0.31,
        range_total_signals=200,
        position=0,
        bars_in_position=0,
        band_lo=0.30,
        band_hi=0.70,
        under_band_release_hysteresis=0.02,
    )
    assert d.mode == MODE_FORCE_FLAT
    assert "release_hyst" in d.reason or "under_flat" in d.reason


@pytest.mark.unit
def test_in_band_035_passthrough_after_release() -> None:
    d = decide_stage2_participation(
        enabled=True,
        range_flat_ratio=0.35,
        range_total_signals=200,
        position=0,
        bars_in_position=0,
        band_lo=0.30,
        under_band_release_hysteresis=0.02,
    )
    assert d.mode == MODE_PASSTHROUGH
    assert d.reason == "in_band"


@pytest.mark.unit
def test_under_flat_max_dwell_force_exit() -> None:
    d = decide_stage2_participation(
        enabled=True,
        range_flat_ratio=0.25,
        range_total_signals=200,
        position=1,
        bars_in_position=120,
        max_hold_bars=90,
        band_lo=0.30,
    )
    assert d.mode == MODE_FORCE_EXIT
    assert d.force_flatten is False
    assert d.force_time_stop is True
    assert "max_dwell" in d.reason


@pytest.mark.unit
def test_sticky_under_band_max_dwell_force_exit() -> None:
    """Live forensics: flat~0.319 sticky zone must FORCE_EXIT (not forever FORCE_HOLD)."""
    d = decide_stage2_participation(
        enabled=True,
        range_flat_ratio=0.319,
        range_total_signals=500,
        position=1,
        bars_in_position=60,
        max_hold_bars=50,
        band_lo=0.30,
        under_band_release_hysteresis=0.02,
        force_exit_on_sticky_under=True,
    )
    assert d.mode == MODE_FORCE_EXIT
    assert d.force_flatten is False
    assert d.force_time_stop is True
    assert "sticky" in d.reason


@pytest.mark.unit
def test_stage2_runtime_release_hyst_zero_passthrough_at_0319() -> None:
    """Live forensics 2026-08-13: flat 0.319 + hyst 0.0 is in-band PASSTHROUGH."""
    d = decide_stage2_participation(
        enabled=True,
        range_flat_ratio=0.319,
        range_total_signals=500,
        position=1,
        bars_in_position=40,
        max_hold_bars=120,
        band_lo=0.30,
        band_hi=0.70,
        under_band_release_hysteresis=0.0,
    )
    assert d.mode == MODE_PASSTHROUGH
    assert d.reason == "in_band"


@pytest.mark.unit
def test_in_band_expectancy_gap_default_passthrough() -> None:
    """In-band FORCE_EXIT under exp gap is theater — default PASSTHROUGH for PPO."""
    d = decide_stage2_participation(
        enabled=True,
        range_flat_ratio=0.45,
        range_total_signals=500,
        position=1,
        bars_in_position=70,
        max_hold_bars=60,
        band_lo=0.30,
        band_hi=0.70,
        expectancy_gap=0.08,
    )
    assert d.mode == MODE_PASSTHROUGH
    assert d.force_time_stop is False
    assert d.force_flatten is False


@pytest.mark.unit
def test_in_band_expectancy_gap_max_dwell_force_exit() -> None:
    """Opt-in: under exp gap, in-band zombies time-stop after max_hold (no flatten)."""
    d = decide_stage2_participation(
        enabled=True,
        range_flat_ratio=0.45,
        range_total_signals=500,
        position=1,
        bars_in_position=70,
        max_hold_bars=60,
        band_lo=0.30,
        band_hi=0.70,
        expectancy_gap=0.08,
        force_exit_on_expectancy_gap=True,
    )
    assert d.mode == MODE_FORCE_EXIT
    assert d.force_flatten is False
    assert d.force_time_stop is True
    assert "expectancy_gap" in d.reason


@pytest.mark.unit
def test_in_band_no_gap_no_force_exit() -> None:
    d = decide_stage2_participation(
        enabled=True,
        range_flat_ratio=0.45,
        range_total_signals=500,
        position=1,
        bars_in_position=70,
        max_hold_bars=60,
        expectancy_gap=0.0,
    )
    assert d.mode == MODE_PASSTHROUGH


@pytest.mark.unit
def test_under_flat_in_position_hold_no_reverse() -> None:
    """Over-trading + open pos: hold-only (no reverse thrash) until max-dwell exit."""
    d = decide_stage2_participation(
        enabled=True,
        range_flat_ratio=0.28,
        range_total_signals=500,
        position=1,
        bars_in_position=10,
        max_hold_bars=120,
        band_lo=0.30,
    )
    assert d.mode == MODE_FORCE_HOLD
    assert d.action_override is not None
    assert d.action_override[0] == 0.0
    assert d.force_flatten is False
    assert d.suppress_flatten is False


@pytest.mark.unit
def test_fencepost_02996_empty_force_flat() -> None:
    """PID 19776: 0.2996 empty must FORCE_FLAT (not PASSTHROUGH chatter at 0.30)."""
    d = decide_stage2_participation(
        enabled=True,
        range_flat_ratio=0.2996,
        range_total_signals=35000,
        position=0,
        bars_in_position=0,
        band_lo=0.30,
        band_hi=0.70,
        under_band_release_hysteresis=0.02,
    )
    assert d.mode == MODE_FORCE_FLAT


@pytest.mark.unit
def test_fencepost_02996_in_position_force_hold() -> None:
    """True under-exam in a trade: no reverse (FORCE_HOLD) until geometry/max-dwell."""
    d = decide_stage2_participation(
        enabled=True,
        range_flat_ratio=0.2996,
        range_total_signals=35000,
        position=1,
        bars_in_position=10,
        max_hold_bars=120,
        band_lo=0.30,
        under_band_release_hysteresis=0.02,
    )
    assert d.mode == MODE_FORCE_HOLD


@pytest.mark.unit
def test_settle_corridor_empty_still_force_flat() -> None:
    """0.305 empty: stay suppressed until 0.32 so the next open cannot knock below 0.30."""
    d = decide_stage2_participation(
        enabled=True,
        range_flat_ratio=0.305,
        range_total_signals=500,
        position=0,
        bars_in_position=0,
        band_lo=0.30,
        under_band_release_hysteresis=0.02,
    )
    assert d.mode == MODE_FORCE_FLAT


@pytest.mark.unit
def test_settle_corridor_in_position_passthrough_not_hold_puppet() -> None:
    """0.305–0.319 in a trade is exam-in-band: PASSTHROUGH, not 90% FORCE_HOLD."""
    d = decide_stage2_participation(
        enabled=True,
        range_flat_ratio=0.319,
        range_total_signals=500,
        position=1,
        bars_in_position=40,
        max_hold_bars=120,
        band_lo=0.30,
        under_band_release_hysteresis=0.02,
    )
    assert d.mode == MODE_PASSTHROUGH
    assert d.reason == "under_flat_settle_in_exam_passthrough"


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
            MODE_FORCE_EXIT: 3,
            MODE_PASSTHROUGH: 100,
        }
    )
    assert t["participation_overrides_total"] == 55
    assert t["participation_force_open"] == 10
    assert t["participation_force_exit"] == 3


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


@pytest.mark.unit
def test_rolling_under_band_force_flat_even_if_cumulative_in_band() -> None:
    """IMU: rolling 15% / cumulative 35% must FORCE_FLAT (live 13/08 bleed)."""
    d = decide_stage2_participation(
        enabled=True,
        range_flat_ratio=0.35,
        rolling_flat_ratio=0.15,
        range_total_signals=28000,
        position=0,
        bars_in_position=0,
        band_lo=0.30,
        band_hi=0.70,
        under_band_release_hysteresis=0.0,
    )
    assert d.mode == MODE_FORCE_FLAT
    assert "under_flat" in d.reason


@pytest.mark.unit
def test_live_flat_018_force_flat() -> None:
    """PID 22168: cumulative 18.5% + pos=0 → FORCE_FLAT, never PASSTHROUGH."""
    d = decide_stage2_participation(
        enabled=True,
        range_flat_ratio=0.1854,
        range_total_signals=28817,
        position=0,
        bars_in_position=0,
        under_band_release_hysteresis=0.0,
    )
    assert d.mode == MODE_FORCE_FLAT


@pytest.mark.unit
def test_occupancy_control_flat_is_min_of_rolling_and_cumulative() -> None:
    assert occupancy_control_flat(cumulative_flat=0.35, rolling_flat=0.15) == pytest.approx(
        0.15
    )
    assert occupancy_control_flat(cumulative_flat=0.18, rolling_flat=None) == pytest.approx(
        0.18
    )


@pytest.mark.unit
def test_occupancy_control_over_is_max_of_rolling_and_cumulative() -> None:
    """Over-band IMU: exam-empty (high cumulative) cannot hide behind in-band rolling."""
    assert occupancy_control_over(cumulative_flat=0.90, rolling_flat=0.50) == pytest.approx(
        0.90
    )
    assert occupancy_control_over(cumulative_flat=0.50, rolling_flat=0.90) == pytest.approx(
        0.90
    )
    assert occupancy_control_over(cumulative_flat=0.50, rolling_flat=None) == pytest.approx(
        0.50
    )


@pytest.mark.unit
def test_force_open_stop_from_atr_dwell_scale_and_constitution_clip() -> None:
    """Documented ATR floor: atr=0.002, min_dwell=8 → 0.002×√8, clipped to [0.0004, 0.01]."""
    atr = 0.002
    dwell = 8
    floor = atr * (dwell ** 0.5)
    stop = force_open_stop_from_atr(atr_pct=atr, min_dwell_bars=dwell)
    assert stop == pytest.approx(floor)
    assert 0.0004 <= stop <= 0.01
    assert force_open_stop_from_atr(atr_pct=0.05, min_dwell_bars=dwell) == pytest.approx(0.01)
    assert force_open_stop_from_atr(atr_pct=0.0, min_dwell_bars=dwell) == pytest.approx(0.0004)
    # Envelope FORCE_OPEN still constitution-clips a caller-supplied macro stop.
    d = decide_stage2_participation(
        enabled=True,
        range_flat_ratio=0.90,
        range_total_signals=200,
        position=0,
        bars_in_position=0,
        stop_pct=0.05,
        target_pct=0.08,
    )
    assert d.mode == MODE_FORCE_OPEN
    assert d.action_override is not None
    assert d.action_override[2] == pytest.approx(0.01)
    assert d.action_override[2] <= 0.01


@pytest.mark.unit
def test_cloud_failure_replica_high_cumulative_in_band_rolling_force_open() -> None:
    """Live cloud S2 stall: cum 0.903 + rolling 0.50 empty must FORCE_OPEN.

    Old rolling-only over_flat PASSTHROUGHed here. That PASSTHROUGH is the P0.
    """
    d = decide_stage2_participation(
        enabled=True,
        range_flat_ratio=0.903,
        rolling_flat_ratio=0.50,
        range_total_signals=8000,
        position=0,
        bars_in_position=0,
        band_lo=0.30,
        band_hi=0.70,
        min_signals=50,
    )
    assert d.mode == MODE_FORCE_OPEN
    assert "over_flat" in d.reason


@pytest.mark.unit
def test_symmetric_over_flat_rolling_high_cumulative_in_band_force_open() -> None:
    d = decide_stage2_participation(
        enabled=True,
        range_flat_ratio=0.50,
        rolling_flat_ratio=0.90,
        range_total_signals=8000,
        position=0,
        bars_in_position=0,
        band_lo=0.30,
        band_hi=0.70,
        min_signals=50,
    )
    assert d.mode == MODE_FORCE_OPEN
    assert "over_flat" in d.reason


@pytest.mark.unit
def test_both_imus_in_band_passthrough() -> None:
    d = decide_stage2_participation(
        enabled=True,
        range_flat_ratio=0.50,
        rolling_flat_ratio=0.50,
        range_total_signals=8000,
        position=0,
        bars_in_position=0,
        band_lo=0.30,
        band_hi=0.70,
        min_signals=50,
    )
    assert d.mode == MODE_PASSTHROUGH
    assert d.reason == "in_band"


@pytest.mark.unit
def test_both_imus_over_flat_force_open() -> None:
    d = decide_stage2_participation(
        enabled=True,
        range_flat_ratio=0.90,
        rolling_flat_ratio=0.90,
        range_total_signals=8000,
        position=0,
        bars_in_position=0,
        band_lo=0.30,
        band_hi=0.70,
        min_signals=50,
    )
    assert d.mode == MODE_FORCE_OPEN
    assert "over_flat" in d.reason


@pytest.mark.unit
def test_dual_fire_under_band_wins_over_force_open() -> None:
    """cum=0.90 over-flat AND roll=0.15 under-flat → FORCE_FLAT (under-band first)."""
    d = decide_stage2_participation(
        enabled=True,
        range_flat_ratio=0.90,
        rolling_flat_ratio=0.15,
        range_total_signals=8000,
        position=0,
        bars_in_position=0,
        band_lo=0.30,
        band_hi=0.70,
        min_signals=50,
        under_band_release_hysteresis=0.0,
    )
    assert d.mode == MODE_FORCE_FLAT
    assert "under_flat" in d.reason


@pytest.mark.unit
def test_pre_caps_never_disables_envelope_on_quality_lock() -> None:
    """Airframe law: quality lock must not set participation_envelope_enabled=False."""
    from pathlib import Path

    src = Path("lumina_core/birth/stage_loop_rollout_pre_caps.py").read_text(
        encoding="utf-8"
    )
    assert "participation_envelope_enabled = False" not in src
    assert "Quality window: PASSTHROUGH so geometry can finish" not in src
    assert "quality_lock_active" not in src


@pytest.mark.unit
def test_s3_exam_cumulative_in_band_passthrough_despite_rolling_under() -> None:
    """Live S3 exam: cum=0.577 in 0.28–0.72, rolling=0.278 must not FORCE_FLAT."""
    d = decide_stage2_participation(
        enabled=True,
        range_flat_ratio=0.577,
        rolling_flat_ratio=0.278,
        range_total_signals=8000,
        position=0,
        bars_in_position=0,
        band_lo=0.28,
        band_hi=0.72,
        hysteresis=0.0,
        under_band_release_hysteresis=0.0,
        min_signals=50,
        cumulative_in_band_passthrough=True,
    )
    assert d.mode == MODE_PASSTHROUGH
    assert d.reason == "exam_cumulative_in_band"
    assert d.action_override is None


@pytest.mark.unit
def test_s2_dual_imu_unchanged_rolling_under_force_flat() -> None:
    """S2 keeps dual IMU: rolling 0.278 with band_lo 0.30 still FORCE_FLAT."""
    d = decide_stage2_participation(
        enabled=True,
        range_flat_ratio=0.577,
        rolling_flat_ratio=0.278,
        range_total_signals=8000,
        position=0,
        bars_in_position=0,
        band_lo=0.30,
        band_hi=0.70,
        min_signals=50,
        cumulative_in_band_passthrough=False,
    )
    assert d.mode == MODE_FORCE_FLAT


@pytest.mark.unit
def test_s3_cumulative_over_band_still_force_open() -> None:
    """Flag does not disable plant when exam cumulative is still empty."""
    d = decide_stage2_participation(
        enabled=True,
        range_flat_ratio=0.90,
        rolling_flat_ratio=0.50,
        range_total_signals=8000,
        position=0,
        bars_in_position=0,
        band_lo=0.28,
        band_hi=0.72,
        hysteresis=0.0,
        min_signals=50,
        cumulative_in_band_passthrough=True,
    )
    assert d.mode == MODE_FORCE_OPEN


@pytest.mark.unit
def test_participation_telemetry_dumps_passthrough() -> None:
    telem = participation_telemetry(
        {
            MODE_FORCE_OPEN: 10,
            MODE_FORCE_HOLD: 20,
            MODE_FORCE_FLAT: 30,
            MODE_FORCE_EXIT: 4,
            MODE_PASSTHROUGH: 100,
        }
    )
    assert telem["participation_force_open"] == 10
    assert telem["participation_force_hold"] == 20
    assert telem["participation_force_flat"] == 30
    assert telem["participation_force_exit"] == 4
    assert telem["participation_passthrough"] == 100
    assert telem["participation_overrides_total"] == 64

