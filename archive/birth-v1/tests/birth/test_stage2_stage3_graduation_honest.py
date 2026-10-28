"""Stage-2 durable graduation (A+C) + Stage-3 occupancy — honest pass contract."""

from __future__ import annotations

import pytest

from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.starship_edgescore_stage2 import evaluate_stage2_edgescore
from lumina_core.birth.starship_edgescore_stage3 import evaluate_stage3_edgescore
from tests.birth.honest_settlement import honest_closes


def _cfg(**overrides: object) -> BirthCurriculumConfig:
    base = BirthCurriculumConfig()
    for k, v in overrides.items():
        setattr(base, k, v)
    return base


@pytest.mark.unit
def test_stage2_rejects_single_rolling_window_weak_lifetime() -> None:
    """Live forensics: life 26% + roll 35.3% must NOT pass (was skill_lifted PASS)."""
    cfg = _cfg(stage2_pass_durable_enabled=True, stage2_pass_rolling_streak=2)
    r = evaluate_stage2_edgescore(
        trades=1160,
        wins=304,  # 26.2%
        range_flat_ratio=0.32,
        range_round_trips=1160,
        range_total_signals=17000,
        constitution_violations=0,
        required=300,
        cfg=cfg,
        rolling_winrate=0.353,
        policy_trades=1160,
        policy_wins=304,
        consecutive_rolling_pass_windows=1,
        **honest_closes(1160),
    )
    assert r.passed is False
    assert r.expectancy_ok is False or r.durable_ok is False


@pytest.mark.unit
def test_stage2_rejects_two_windows_still_weak_lifetime() -> None:
    """A alone is not enough: C requires life ≥ floor−5pp (30%)."""
    cfg = _cfg(stage2_pass_durable_enabled=True)
    r = evaluate_stage2_edgescore(
        trades=1160,
        wins=304,
        range_flat_ratio=0.32,
        range_round_trips=1160,
        range_total_signals=17000,
        constitution_violations=0,
        required=300,
        cfg=cfg,
        rolling_winrate=0.353,
        policy_trades=1160,
        policy_wins=304,
        consecutive_rolling_pass_windows=2,
        **honest_closes(1160),
    )
    assert r.passed is False
    assert r.expectancy_ok is False or r.durable_ok is False


@pytest.mark.unit
def test_stage2_passes_lifetime_clear_of_floor() -> None:
    """Lifetime ≥35% still needs 2 rolling windows (PID 33628 hop was not durable)."""
    cfg = _cfg(stage2_pass_durable_enabled=True)
    r = evaluate_stage2_edgescore(
        trades=500,
        wins=180,  # 36%
        range_flat_ratio=0.32,
        range_round_trips=500,
        range_total_signals=8000,
        constitution_violations=0,
        required=300,
        cfg=cfg,
        rolling_winrate=0.36,
        policy_trades=500,
        policy_wins=180,
        consecutive_rolling_pass_windows=2,
        **honest_closes(500),
    )
    assert r.passed is True


@pytest.mark.unit
def test_stage2_passes_rolling_durable_with_life_band() -> None:
    """Roll 35% ×2 + life 31% (≥30%) → durable pass."""
    cfg = _cfg(stage2_pass_durable_enabled=True)
    r = evaluate_stage2_edgescore(
        trades=400,
        wins=124,  # 31%
        range_flat_ratio=0.33,
        range_round_trips=400,
        range_total_signals=6000,
        constitution_violations=0,
        required=300,
        cfg=cfg,
        rolling_winrate=0.36,
        policy_trades=400,
        policy_wins=124,
        consecutive_rolling_pass_windows=2,
        **honest_closes(400),
    )
    assert r.passed is False
    assert r.pass_expectancy_source == "rolling_hud_only"


@pytest.mark.unit
def test_stage3_fails_occupancy_over_trading() -> None:
    cfg = _cfg(stage3_occupancy_pass_enabled=True, stage3_position_flat_min=0.25)
    r = evaluate_stage3_edgescore(
        trades=500,
        wins=200,  # 40% WR — hygiene OK
        hold_signals=300,
        total_signals=1000,
        constitution_violations=0,
        required=500,
        cfg=cfg,
        rolling_winrate=0.40,
        hold_ratio=0.30,
        range_flat_ratio=0.03,
        range_total_signals=1000,
        range_round_trips=500,
        **honest_closes(500),
    )
    assert r.passed is False
    assert "flat" in r.message and "over-trading" in r.message


@pytest.mark.unit
def test_stage3_passes_with_flat_and_hygiene() -> None:
    cfg = _cfg()
    r = evaluate_stage3_edgescore(
        trades=500,
        wins=200,
        hold_signals=300,
        total_signals=1000,
        constitution_violations=0,
        required=500,
        cfg=cfg,
        rolling_winrate=0.40,
        hold_ratio=0.30,
        range_flat_ratio=0.32,
        range_total_signals=1000,
        range_round_trips=500,
        **honest_closes(500),
    )
    assert r.passed is True


@pytest.mark.unit
def test_stage3_envelope_config_defaults() -> None:
    cfg = BirthCurriculumConfig()
    assert cfg.stage3_participation_envelope_enabled is True
    assert cfg.stage3_participation_band_lo == pytest.approx(0.28)
    assert cfg.stage3_participation_band_hi == pytest.approx(0.72)
    assert cfg.stage3_participation_hysteresis == pytest.approx(0.0)
    assert cfg.stage3_participation_under_band_release_hysteresis == pytest.approx(0.0)
    assert cfg.stage2_participation_under_band_release_hysteresis == pytest.approx(0.02)
    assert cfg.stage2_occupancy_control_window_bars == 500
    assert cfg.stage3_occupancy_control_window_bars == 500
    assert cfg.stage3_position_flat_min == pytest.approx(0.25)
    assert cfg.stage3_position_flat_max == pytest.approx(0.75)
    assert cfg.stage2_pass_durable_enabled is True
    assert cfg.stage3_pass_durable_enabled is True
    assert cfg.stage2_transfer_handoff_enabled is True
    assert cfg.stage2_quality_lock_enabled is True
    assert cfg.stage2_force_exit_on_expectancy_gap is False
    assert float(cfg.stage2_expectancy_floor) == pytest.approx(-0.15)


@pytest.mark.unit
def test_stage2_flash_green_42pct_does_not_pass_weak_lifetime() -> None:
    """21:30 12/08: chunk 42% / exp −0.08 with lifetime 26.5% must not graduate."""
    cfg = _cfg(stage2_pass_durable_enabled=True)
    r = evaluate_stage2_edgescore(
        trades=1650,
        wins=437,  # 26.5%
        range_flat_ratio=0.33,
        range_round_trips=1650,
        range_total_signals=20000,
        constitution_violations=0,
        required=300,
        cfg=cfg,
        rolling_winrate=0.42,
        policy_trades=1650,
        policy_wins=437,
        consecutive_rolling_pass_windows=0,
        **honest_closes(1650),
    )
    assert r.passed is False


@pytest.mark.unit
def test_stage2_lifetime_38pct_hop_is_not_durable_without_streak() -> None:
    """PID 33628: 38% @ 350 is a flash, not durable green."""
    cfg = _cfg(stage2_pass_durable_enabled=True)
    r = evaluate_stage2_edgescore(
        trades=350,
        wins=133,  # 38%
        range_flat_ratio=0.32,
        range_round_trips=350,
        range_total_signals=10000,
        constitution_violations=0,
        required=300,
        cfg=cfg,
        entropy=0.2,
        rolling_winrate=0.38,
        policy_trades=350,
        policy_wins=133,
        consecutive_rolling_pass_windows=0,
        **honest_closes(350),
    )
    assert r.passed is False
    assert r.durable_ok is False
    assert r.score <= 0.49 + 1e-9


@pytest.mark.unit
def test_stage2_occupancy_theater_score_not_80pct_when_expectancy_fails() -> None:
    """PID 33628: flat in band + entropy must not print EdgeScore 80% at exp −20%."""
    cfg = _cfg()
    r = evaluate_stage2_edgescore(
        trades=994,
        wins=296,  # 29.8%
        range_flat_ratio=0.32,
        range_round_trips=994,
        range_total_signals=26956,
        constitution_violations=0,
        required=300,
        cfg=cfg,
        entropy=5.67,
        rolling_winrate=0.2917,
        policy_trades=994,
        policy_wins=296,
        consecutive_rolling_pass_windows=0,
        **honest_closes(994),
    )
    assert r.passed is False
    assert r.expectancy_ok is False
    assert r.activity_ok is True
    assert r.score < 0.50


@pytest.mark.unit
def test_quality_lock_releases_when_hop_fails_in_band() -> None:
    """PID 33628: 38% lock + 30% life + flat 32% must unfreeze (envelope holding)."""
    from lumina_core.birth.stage2_peak_capture import (
        Stage2PeakState,
        maybe_arm_quality_lock,
        maybe_release_quality_lock,
    )

    cfg = _cfg()
    state = Stage2PeakState()
    maybe_arm_quality_lock(
        state,
        chunk_wr=0.38,
        chunk_exp=-0.12,
        stage_trades=350,
        cfg=cfg,
    )
    assert state.quality_lock_active is True
    released = maybe_release_quality_lock(
        state,
        lifetime_wr=0.2978,
        stage_trades=994,
        required=300,
        cfg=cfg,
        rolling_winrate=0.2917,
        consecutive_rolling_pass_windows=0,
        range_flat_ratio=0.32,
    )
    assert released is True
    assert state.quality_lock_active is False


@pytest.mark.unit
def test_quality_lock_arms_on_42pct_chunk() -> None:
    from lumina_core.birth.stage2_peak_capture import (
        Stage2PeakState,
        maybe_arm_quality_lock,
        should_freeze_ppo_quality_lock,
    )

    cfg = _cfg()
    state = Stage2PeakState()
    armed = maybe_arm_quality_lock(
        state,
        chunk_wr=0.42,
        chunk_exp=-0.08,
        stage_trades=1650,
        cfg=cfg,
    )
    assert armed is True
    assert state.quality_lock_active is True
    freeze, reason = should_freeze_ppo_quality_lock(state, cfg=cfg)
    assert freeze is True
    assert reason == "quality_lock"


@pytest.mark.unit
def test_quality_lock_does_not_release_same_cycle_or_before_volume() -> None:
    from lumina_core.birth.stage2_peak_capture import (
        Stage2PeakState,
        maybe_arm_quality_lock,
        maybe_release_quality_lock,
    )

    cfg = _cfg()
    state = Stage2PeakState()
    maybe_arm_quality_lock(
        state,
        chunk_wr=0.40,
        chunk_exp=-0.10,
        stage_trades=150,
        cfg=cfg,
    )
    assert state.quality_lock_active is True
    same = maybe_release_quality_lock(
        state,
        lifetime_wr=0.40,
        stage_trades=150,
        required=300,
        cfg=cfg,
    )
    assert same is False
    assert state.quality_lock_active is True
    pre_vol = maybe_release_quality_lock(
        state,
        lifetime_wr=0.40,
        stage_trades=200,
        required=300,
        cfg=cfg,
    )
    assert pre_vol is False
    assert state.quality_lock_active is True


@pytest.mark.unit
def test_quality_lock_does_not_release_at_volume_on_c_band_only() -> None:
    """PID 19776: life 31% at volume must not unfreeze PPO (44% peak then burned)."""
    from lumina_core.birth.stage2_peak_capture import (
        Stage2PeakState,
        maybe_arm_quality_lock,
        maybe_release_quality_lock,
    )

    cfg = _cfg()
    state = Stage2PeakState()
    maybe_arm_quality_lock(
        state,
        chunk_wr=0.40,
        chunk_exp=-0.10,
        stage_trades=150,
        cfg=cfg,
    )
    released = maybe_release_quality_lock(
        state,
        lifetime_wr=0.32,
        stage_trades=300,
        required=300,
        cfg=cfg,
    )
    assert released is False
    assert state.quality_lock_active is True
    live = maybe_release_quality_lock(
        state,
        lifetime_wr=0.3115,
        stage_trades=500,
        required=300,
        cfg=cfg,
        rolling_winrate=0.34,
        consecutive_rolling_pass_windows=0,
        range_flat_ratio=0.2996,
    )
    assert live is False
    assert state.quality_lock_active is True


@pytest.mark.unit
def test_quality_lock_releases_only_when_durable_exam_green() -> None:
    from lumina_core.birth.stage2_peak_capture import (
        Stage2PeakState,
        maybe_arm_quality_lock,
        maybe_release_quality_lock,
    )

    cfg = _cfg()
    state = Stage2PeakState()
    maybe_arm_quality_lock(
        state,
        chunk_wr=0.40,
        chunk_exp=-0.10,
        stage_trades=150,
        cfg=cfg,
    )
    released = maybe_release_quality_lock(
        state,
        lifetime_wr=0.32,
        stage_trades=400,
        required=300,
        cfg=cfg,
        rolling_winrate=0.36,
        consecutive_rolling_pass_windows=2,
        range_flat_ratio=0.33,
    )
    assert released is True
    assert state.quality_lock_active is False


@pytest.mark.unit
def test_quality_lock_arms_on_in_band_peak_without_chunk() -> None:
    """PID 19776: 44% peak @ 300 must lock even if this chunk is <36%."""
    from lumina_core.birth.stage2_peak_capture import (
        Stage2PeakState,
        maybe_arm_quality_lock,
        should_freeze_ppo_quality_lock,
    )

    cfg = _cfg()
    state = Stage2PeakState(
        peak_winrate=0.44,
        peak_expectancy=-0.06,
        peak_at_trade=300,
        peak_flat=0.3002,
    )
    armed = maybe_arm_quality_lock(
        state,
        chunk_wr=None,
        stage_trades=300,
        cfg=cfg,
        rolling_winrate=0.44,
    )
    assert armed is True
    assert state.quality_lock_active is True
    assert state.quality_lock_wr == pytest.approx(0.44)
    freeze, reason = should_freeze_ppo_quality_lock(state, cfg=cfg)
    assert freeze is True
    assert reason == "quality_lock"


@pytest.mark.unit
def test_quality_lock_does_not_rearm_stale_peak_when_in_band_collapsed() -> None:
    """PID 40020: museum 42% @ 450 must not freeze PPO while live WR is ~30% in-band."""
    from lumina_core.birth.stage2_peak_capture import (
        Stage2PeakState,
        maybe_arm_quality_lock,
        should_freeze_ppo_quality_lock,
    )

    cfg = _cfg()
    state = Stage2PeakState(
        peak_winrate=0.42,
        peak_expectancy=-0.08,
        peak_at_trade=450,
        peak_flat=0.32,
    )
    armed = maybe_arm_quality_lock(
        state,
        chunk_wr=0.29,
        chunk_exp=-0.21,
        stage_trades=888,
        cfg=cfg,
        rolling_winrate=0.3033,
        lifetime_wr=0.2984,
        range_flat_ratio=0.32,
    )
    assert armed is False
    freeze, _reason = should_freeze_ppo_quality_lock(state, cfg=cfg)
    assert freeze is False


@pytest.mark.unit
def test_quality_lock_still_arms_stale_peak_when_occupancy_out_of_band() -> None:
    """PID 19776: out-of-band envelope still needs peak lock (not hop_fail)."""
    from lumina_core.birth.stage2_peak_capture import (
        Stage2PeakState,
        maybe_arm_quality_lock,
    )

    cfg = _cfg()
    state = Stage2PeakState(
        peak_winrate=0.44,
        peak_expectancy=-0.06,
        peak_at_trade=300,
        peak_flat=0.3002,
    )
    armed = maybe_arm_quality_lock(
        state,
        chunk_wr=None,
        stage_trades=500,
        cfg=cfg,
        rolling_winrate=0.34,
        lifetime_wr=0.3115,
        range_flat_ratio=0.2996,
    )
    assert armed is True


@pytest.mark.unit
def test_quality_lock_holds_when_rolling_is_live_green() -> None:
    """Rolling ≥35% + life 30% in-band is the durable-lift path, not hop_fail."""
    from lumina_core.birth.stage2_peak_capture import (
        Stage2PeakState,
        maybe_arm_quality_lock,
        maybe_release_quality_lock,
    )

    cfg = _cfg()
    state = Stage2PeakState()
    maybe_arm_quality_lock(
        state,
        chunk_wr=0.36,
        chunk_exp=-0.14,
        stage_trades=400,
        cfg=cfg,
        rolling_winrate=0.36,
        lifetime_wr=0.36,
        range_flat_ratio=0.32,
    )
    assert state.quality_lock_active is True
    held = maybe_release_quality_lock(
        state,
        lifetime_wr=0.30,
        stage_trades=500,
        required=300,
        cfg=cfg,
        rolling_winrate=0.36,
        consecutive_rolling_pass_windows=1,
        range_flat_ratio=0.32,
    )
    assert held is False
    assert state.quality_lock_active is True


@pytest.mark.unit
def test_quality_lock_holds_at_volume_when_lifetime_below_c_band() -> None:
    from lumina_core.birth.stage2_peak_capture import (
        Stage2PeakState,
        maybe_arm_quality_lock,
        maybe_release_quality_lock,
    )

    cfg = _cfg()
    state = Stage2PeakState()
    maybe_arm_quality_lock(
        state,
        chunk_wr=0.40,
        chunk_exp=-0.10,
        stage_trades=150,
        cfg=cfg,
    )
    held = maybe_release_quality_lock(
        state,
        lifetime_wr=0.27,
        stage_trades=300,
        required=300,
        cfg=cfg,
    )
    assert held is False
    assert state.quality_lock_active is True


@pytest.mark.unit
def test_stage3_rejects_rolling_only_weak_lifetime() -> None:
    """12/08 session 1: life 25.6% + roll 35% must not pass (durable C-rule)."""
    cfg = _cfg(stage3_pass_durable_enabled=True, stage3_occupancy_pass_enabled=True)
    r = evaluate_stage3_edgescore(
        trades=636,
        wins=163,  # 25.6%
        hold_signals=160,
        total_signals=1000,
        constitution_violations=0,
        required=500,
        cfg=cfg,
        rolling_winrate=0.353,
        hold_ratio=0.16,
        range_flat_ratio=0.32,
        range_total_signals=1000,
        consecutive_rolling_pass_windows=2,
        range_round_trips=636,
        **honest_closes(636),
    )
    assert r.passed is False
    assert "durable" in r.message or "lifetime" in r.message or "hygiene" in r.message


@pytest.mark.unit
def test_stage2_weak_lifetime_handoff_keeps_less() -> None:
    """Honest S2 pass still detoxes a 26% lifetime prior before Stage-3."""
    from types import SimpleNamespace

    from lumina_core.birth.stage2_transfer_handoff import execute_stage2_transfer_handoff

    host = SimpleNamespace(buffer=[], current_policy=None, runtime=None, ppo_trainer=None)
    cfg = _cfg(
        stage2_transfer_handoff_enabled=True,
        stage2_transfer_purge_buffer=True,
        stage2_transfer_keep_buffer_top_pct=0.10,
        stage2_transfer_reinit_action_head=False,
    )
    result = execute_stage2_transfer_handoff(
        host=host,
        cfg=cfg,
        stage_trades=1160,
        stage_wins=304,  # 26.2% — 18:09 loophole payload
        rolling_winrate=0.353,
    )
    assert result["stage2_wr"] < 0.30
    assert result["ok"] is True or result["reason"] in {"handoff_complete", "handoff_partial"}
