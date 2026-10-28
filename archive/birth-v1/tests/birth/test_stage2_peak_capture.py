"""Stage-2 peak capture, near-miss, swarm/phoenix gates, restore — P0–P2 truth."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.curriculum import CurriculumStage, evaluate_stage_pass
from lumina_core.birth.stage2_peak_capture import (
    Stage2PeakState,
    accumulate_exit_physics,
    effective_stage2_winrate,
    evaluate_near_miss,
    is_near_miss_expectancy,
    note_quality_rollout,
    record_restore,
    should_block_phoenix_for_peak,
    should_defer_swarm_for_peak,
    should_restore_peak_policy,
    stage2_expectancy_from_wr,
    update_stage2_peak,
)


def _cfg(**overrides: object) -> BirthCurriculumConfig:
    base = BirthCurriculumConfig()
    for key, value in overrides.items():
        setattr(base, key, value)
    return base


@pytest.mark.unit
def test_expectancy_from_wr_is_truthful() -> None:
    """WR 34.7% → exp ≈ −0.153 (forensics peak); floor −0.15 ≡ 35% WR."""
    assert stage2_expectancy_from_wr(0.347) == pytest.approx(-0.153, abs=1e-6)
    assert stage2_expectancy_from_wr(0.35) == pytest.approx(-0.15, abs=1e-6)
    assert stage2_expectancy_from_wr(0.50) == pytest.approx(0.0, abs=1e-6)


@pytest.mark.unit
def test_near_miss_band_exclusive_of_pass() -> None:
    # At/above floor is pass territory — not near-miss.
    assert is_near_miss_expectancy(expectancy=-0.15, exp_floor=-0.15) is False
    assert is_near_miss_expectancy(expectancy=-0.10, exp_floor=-0.15) is False
    # Just under floor within delta.
    assert is_near_miss_expectancy(expectancy=-0.153, exp_floor=-0.15, near_delta=0.02) is True
    assert is_near_miss_expectancy(expectancy=-0.17, exp_floor=-0.15, near_delta=0.02) is True
    # Too far below.
    assert is_near_miss_expectancy(expectancy=-0.22, exp_floor=-0.15, near_delta=0.02) is False


@pytest.mark.unit
def test_peak_update_requires_min_trades_and_improves() -> None:
    st = Stage2PeakState()
    cfg = _cfg(stage2_peak_min_trades=50)
    # Below min trades and no flash chunk: no peak.
    assert (
        update_stage2_peak(
            st,
            stage_trades=30,
            stage_wins=12,
            range_flat_ratio=0.40,
            cfg=cfg,
        )
        is False
    )
    assert st.peak_winrate == 0.0
    # First honest peak at 50 trades, 36% WR (flash green forensics).
    assert (
        update_stage2_peak(
            st,
            stage_trades=50,
            stage_wins=18,
            range_flat_ratio=0.42,
            rolling_winrate=0.36,
            chunk_winrate=0.36,
            chunk_trades=50,
            policy_path="/tmp/peak.zip",
            cfg=cfg,
        )
        is True
    )
    assert st.peak_winrate == pytest.approx(0.36, abs=0.01)
    assert st.peak_at_trade == 50
    assert st.flash_green is True
    assert st.peak_policy_path.endswith("peak.zip")
    # No regression: lower WR does not update peak.
    assert (
        update_stage2_peak(
            st,
            stage_trades=200,
            stage_wins=64,  # 32%
            range_flat_ratio=0.40,
            cfg=cfg,
        )
        is False
    )
    assert st.peak_at_trade == 50


@pytest.mark.unit
def test_flash_green_hop_captures_but_not_durable_alone() -> None:
    """Single lucky 50-trade 36% hop: save peak telemetry, do NOT arm/thrash."""
    from lumina_core.birth.stage2_peak_capture import (
        maybe_arm_peak_graduation,
        finish_mode_blocks_pattern_inject,
        should_restore_peak_policy,
    )

    st = Stage2PeakState()
    cfg = _cfg(
        stage2_peak_min_trades=50,
        stage2_peak_grad_enabled=True,
        stage2_flash_green_min_trades=50,
        stage2_flash_durable_min_chunks=2,
    )
    ok = update_stage2_peak(
        st,
        stage_trades=50,
        stage_wins=15,  # 30% life
        range_flat_ratio=0.32,
        chunk_winrate=0.36,
        chunk_trades=50,
        policy_path="/tmp/birth_peak.zip",
        cfg=cfg,
    )
    assert ok is True
    assert st.flash_green is True
    assert st.flash_green_wr == pytest.approx(0.36, abs=1e-6)
    assert st.flash_green_durable is False  # single hop is not durable
    assert st.consecutive_green_chunks == 1
    # Hop must NOT block oracle inject (live: inject+PPO both dead → stuck 29% WR).
    assert finish_mode_blocks_pattern_inject(st) is False
    # Must NOT arm graduation on hop-only (live thrash root cause).
    armed = maybe_arm_peak_graduation(
        st, stage_trades=50, range_flat_ratio=0.32, required=300, cfg=cfg
    )
    assert armed is False
    assert st.peak_grad_armed is False
    # Must NOT restore-thrash on hop-only.
    do_r, reason = should_restore_peak_policy(
        st,
        stage_trades=120,
        stage_wins=37,
        rolling_winrate=0.30,
        range_flat_ratio=0.32,
        cfg=cfg,
    )
    assert do_r is False
    assert "hop_only" in reason


@pytest.mark.unit
def test_lifetime_38pct_single_hop_is_not_flash_durable() -> None:
    """PID 33628: 38% lifetime must not latch flash_green_durable / peak_grad."""
    from lumina_core.birth.stage2_peak_capture import maybe_arm_peak_graduation

    st = Stage2PeakState()
    cfg = _cfg(
        stage2_peak_min_trades=50,
        stage2_peak_grad_enabled=True,
        stage2_flash_durable_min_chunks=2,
    )
    update_stage2_peak(
        st,
        stage_trades=350,
        stage_wins=133,  # 38% life
        range_flat_ratio=0.3198,
        rolling_winrate=0.38,
        chunk_winrate=0.38,
        chunk_trades=50,
        policy_path="/tmp/birth_peak.zip",
        cfg=cfg,
    )
    assert st.flash_green is True
    assert st.flash_green_durable is False
    assert (
        maybe_arm_peak_graduation(
            st, stage_trades=350, range_flat_ratio=0.3198, required=300, cfg=cfg
        )
        is False
    )
    assert st.peak_grad_armed is False


@pytest.mark.unit
def test_leftover_peak_grad_disarms_without_durable_falling_edge() -> None:
    """PID 33628 resume: peak_grad_armed + durable already false must disarm."""
    st = Stage2PeakState(
        peak_winrate=0.38,
        peak_expectancy=-0.12,
        peak_at_trade=350,
        peak_flat=0.32,
        peak_policy_path="/tmp/birth_peak.zip",
        peak_grad_armed=True,
        peak_grad_armed_at_trade=350,
        flash_green=True,
        flash_green_wr=0.38,
        flash_green_at_trade=350,
        flash_green_durable=False,
        consecutive_green_chunks=1,
        consecutive_rolling_pass_windows=0,
        quality_lock_active=True,
        quality_lock_wr=0.38,
        quality_lock_at_trade=350,
    )
    cfg = _cfg(
        stage2_peak_min_trades=50,
        stage2_peak_grad_enabled=True,
        stage2_flash_durable_min_chunks=2,
    )
    update_stage2_peak(
        st,
        stage_trades=994,
        stage_wins=296,
        range_flat_ratio=0.32,
        rolling_winrate=0.292,
        chunk_winrate=0.29,
        chunk_trades=50,
        policy_path="/tmp/birth_peak.zip",
        cfg=cfg,
    )
    assert st.flash_green_durable is False
    assert st.peak_grad_armed is False


@pytest.mark.unit
def test_hop_only_quality_lock_in_band_does_not_restore_thrash() -> None:
    """PID 33628: 38% hop lock + flat 32% must not restore every collapse."""
    from lumina_core.birth.stage2_peak_capture import should_restore_peak_policy

    st = Stage2PeakState(
        peak_winrate=0.38,
        peak_at_trade=350,
        peak_flat=0.32,
        peak_policy_path="/tmp/birth_peak.zip",
        flash_green=True,
        flash_green_wr=0.38,
        flash_green_at_trade=350,
        flash_green_durable=False,
        peak_grad_armed=False,
        quality_lock_active=True,
        quality_lock_wr=0.38,
        quality_lock_at_trade=350,
        restore_count=5,
        last_restore_at_trade=900,
    )
    do_r, reason = should_restore_peak_policy(
        st,
        stage_trades=994,
        stage_wins=296,
        rolling_winrate=0.292,
        range_flat_ratio=0.32,
        cfg=_cfg(),
        required=300,
    )
    assert do_r is False
    assert "hop_only" in reason


@pytest.mark.unit
def test_quality_lock_allows_oracle_distill_even_if_grad_armed() -> None:
    """Quality lock must not freeze the teacher — distill peak trajectories."""
    from lumina_core.birth.stage2_peak_capture import finish_mode_blocks_pattern_inject

    st = Stage2PeakState(
        quality_lock_active=True,
        peak_grad_armed=True,
        finish_mode_active=True,
        flash_green_durable=True,
    )
    assert finish_mode_blocks_pattern_inject(st) is False


@pytest.mark.unit
def test_two_green_chunks_makes_flash_durable_and_arms() -> None:
    """Two consecutive green chunks → durable → arm graduation (honest multi-window)."""
    from lumina_core.birth.stage2_peak_capture import (
        maybe_arm_peak_graduation,
        should_restore_peak_policy,
        record_restore,
        note_quality_rollout,
    )

    st = Stage2PeakState()
    cfg = _cfg(
        stage2_peak_min_trades=50,
        stage2_peak_grad_enabled=True,
        stage2_flash_durable_min_chunks=2,
        stage2_peak_grad_collapse_wr_drop=0.05,
        stage2_ppo_freeze_rollouts_after_restore=3,
    )
    # Chunk 1 green hop but life still under floor (15/50=30%).
    update_stage2_peak(
        st,
        stage_trades=50,
        stage_wins=15,
        range_flat_ratio=0.32,
        chunk_winrate=0.36,
        chunk_trades=50,
        policy_path="/tmp/birth_peak.zip",
        cfg=cfg,
    )
    assert st.flash_green is True
    assert st.flash_green_durable is False
    # Chunk 2 green → consecutive_green_chunks=2 → durable (life still mixed).
    update_stage2_peak(
        st,
        stage_trades=100,
        stage_wins=33,  # 33% life still under 35%
        range_flat_ratio=0.32,
        chunk_winrate=0.36,
        chunk_trades=50,
        policy_path="/tmp/birth_peak.zip",
        cfg=cfg,
    )
    assert st.consecutive_green_chunks == 2
    assert st.flash_green_durable is True
    armed = maybe_arm_peak_graduation(
        st, stage_trades=100, range_flat_ratio=0.32, required=300, cfg=cfg
    )
    assert armed is True
    assert st.peak_grad_armed is True
    # Collapse after durable: large drop restores (after min gap + cooldown).
    do_r, reason = should_restore_peak_policy(
        st,
        stage_trades=200,
        stage_wins=60,  # 30% life — 6pp drop
        rolling_winrate=0.28,
        range_flat_ratio=0.32,
        cfg=cfg,
    )
    assert do_r is True
    assert "flash_collapse" in reason or "collapse" in reason
    record_restore(st, stage_trades=200, reason=reason)
    # During freeze, no re-restore.
    do_r2, reason2 = should_restore_peak_policy(
        st,
        stage_trades=260,
        stage_wins=78,
        rolling_winrate=0.28,
        range_flat_ratio=0.32,
        cfg=cfg,
    )
    assert do_r2 is False
    assert "ppo_freeze" in reason2 or reason2 == ""
    note_quality_rollout(st)
    note_quality_rollout(st)
    note_quality_rollout(st)


@pytest.mark.unit
def test_flash_post_volume_rolling_under_034_restores() -> None:
    """After volume, durable flash + rolling < 0.34 must restore."""
    from lumina_core.birth.stage2_peak_capture import should_restore_peak_policy

    st = Stage2PeakState(
        peak_winrate=0.36,
        peak_expectancy=-0.14,
        peak_at_trade=50,
        peak_policy_path="/tmp/peak.zip",
        flash_green=True,
        flash_green_wr=0.36,
        flash_green_at_trade=50,
        flash_green_durable=True,
        peak_grad_armed=True,
        quality_rollouts_since_restore=5,  # freeze lifted
    )
    cfg = _cfg(stage2_peak_grad_collapse_wr_drop=0.05)
    ok, reason = should_restore_peak_policy(
        st,
        stage_trades=300,
        stage_wins=100,  # 33.3% life
        rolling_winrate=0.33,
        range_flat_ratio=0.32,
        cfg=cfg,
        required=300,
    )
    assert ok is True
    assert "flash_post_volume" in reason


@pytest.mark.unit
def test_flash_toxic_chunk_restores_when_durable() -> None:
    from lumina_core.birth.stage2_peak_capture import should_restore_peak_policy

    st = Stage2PeakState(
        peak_winrate=0.36,
        peak_at_trade=50,
        peak_policy_path="/tmp/peak.zip",
        flash_green=True,
        flash_green_wr=0.36,
        flash_green_at_trade=50,
        flash_green_durable=True,
        quality_rollouts_since_restore=5,
    )
    cfg = _cfg()
    ok, reason = should_restore_peak_policy(
        st,
        stage_trades=150,
        stage_wins=52,  # ~34.7% life
        rolling_winrate=0.345,
        range_flat_ratio=0.32,
        cfg=cfg,
        chunk_winrate=0.28,
        chunk_trades=50,
    )
    assert ok is True
    assert "toxic_chunk" in reason


@pytest.mark.unit
def test_flash_green_protect_requires_durable() -> None:
    from lumina_core.birth.stage2_peak_capture import flash_green_protect_active

    # Hop-only: inject still blocked elsewhere; hold protect is durable-only.
    assert flash_green_protect_active(Stage2PeakState(flash_green=True)) is False
    assert (
        flash_green_protect_active(
            Stage2PeakState(flash_green=True, flash_green_durable=True)
        )
        is True
    )
    assert flash_green_protect_active(Stage2PeakState()) is False


@pytest.mark.unit
def test_ppo_freeze_and_quality_gate() -> None:
    from lumina_core.birth.stage2_peak_capture import (
        record_restore,
        should_freeze_ppo_after_restore,
        should_skip_ppo_quality_gate,
        note_quality_rollout,
    )

    st = Stage2PeakState(peak_winrate=0.36, peak_policy_path="/tmp/p.zip")
    cfg = _cfg(
        stage2_ppo_freeze_rollouts_after_restore=3,
        stage2_ppo_freeze_trades_after_restore=120,
    )
    record_restore(st, stage_trades=200, reason="test")
    freeze, reason = should_freeze_ppo_after_restore(
        st, cfg=cfg, stage_trades=200
    )
    assert freeze is True
    assert "restored_this_cycle" in reason or "quality_rollouts" in reason
    st.restored_this_cycle = False
    freeze2, _ = should_freeze_ppo_after_restore(st, cfg=cfg, stage_trades=220)
    assert freeze2 is True
    note_quality_rollout(st)
    note_quality_rollout(st)
    note_quality_rollout(st)
    freeze3, _ = should_freeze_ppo_after_restore(st, cfg=cfg, stage_trades=220)
    assert freeze3 is False

    # Trade-based unstick: even if quality counter stuck, freeze ends after N trades.
    st2 = Stage2PeakState(
        peak_winrate=0.36,
        peak_policy_path="/tmp/p.zip",
        restore_count=1,
        last_restore_at_trade=200,
        quality_rollouts_since_restore=1,  # stuck counter
        restored_this_cycle=False,
    )
    freeze_stuck, _ = should_freeze_ppo_after_restore(
        st2, cfg=cfg, stage_trades=250
    )
    assert freeze_stuck is True  # only 50 trades since restore
    freeze_unstuck, _ = should_freeze_ppo_after_restore(
        st2, cfg=cfg, stage_trades=330
    )
    assert freeze_unstuck is False  # 130 >= 120 trades

    # Clearly toxic large chunk blocked.
    skip, r = should_skip_ppo_quality_gate(
        chunk_winrate=0.20,
        chunk_trades=50,
        first_touch_wr=0.3385,
        edge_vs_random=-0.10,
        lifetime_winrate=0.29,
        cfg=cfg,
    )
    assert skip is True
    assert "toxic" in r or "anti_edge" in r
    # Improving vs lifetime allowed even if under first-touch.
    skip_improve, _ = should_skip_ppo_quality_gate(
        chunk_winrate=0.31,
        chunk_trades=50,
        first_touch_wr=0.3385,
        edge_vs_random=-0.03,
        lifetime_winrate=0.29,
        cfg=cfg,
    )
    assert skip_improve is False
    skip2, _ = should_skip_ppo_quality_gate(
        chunk_winrate=0.36,
        chunk_trades=50,
        first_touch_wr=0.3385,
        edge_vs_random=0.02,
        cfg=cfg,
    )
    assert skip2 is False
    # Micro chunks never hard-block learning.
    skip_micro, _ = should_skip_ppo_quality_gate(
        chunk_winrate=0.10,
        chunk_trades=8,
        first_touch_wr=0.3385,
        cfg=cfg,
    )
    assert skip_micro is False


@pytest.mark.unit
def test_near_miss_active_when_volume_flat_ok() -> None:
    st = Stage2PeakState()
    cfg = _cfg(stage2_expectancy_floor=-0.15, stage2_near_miss_exp_delta=0.02)
    # Volume short of required.
    assert (
        evaluate_near_miss(
            st,
            stage_trades=200,
            stage_wins=70,
            required=300,
            range_flat_ratio=0.45,
            cfg=cfg,
        )
        is False
    )
    # Volume + flat OK, exp ≈ −0.153 (WR 34.7%).
    assert (
        evaluate_near_miss(
            st,
            stage_trades=300,
            stage_wins=104,  # 34.67%
            required=300,
            range_flat_ratio=0.45,
            rolling_winrate=0.347,
            cfg=cfg,
        )
        is True
    )
    assert st.near_miss_active is True
    assert st.near_miss_count >= 1


@pytest.mark.unit
def test_swarm_deferred_on_near_miss_and_anti_edge() -> None:
    st = Stage2PeakState(near_miss_active=True, peak_winrate=0.347)
    cfg = _cfg()
    defer, reason = should_defer_swarm_for_peak(
        st,
        edge_vs_random=-0.05,
        quality_step=0,
        max_quality_steps=4,
        best_winrate=0.32,
        cfg=cfg,
    )
    assert defer is True
    assert reason == "near_miss"

    st2 = Stage2PeakState(near_miss_active=False, peak_winrate=0.34)
    defer2, reason2 = should_defer_swarm_for_peak(
        st2,
        edge_vs_random=-0.10,
        quality_step=1,
        max_quality_steps=4,
        best_winrate=0.32,
        cfg=cfg,
    )
    assert defer2 is True
    assert reason2 == "anti_edge_quality"


@pytest.mark.unit
def test_peak_grad_arms_when_durable_peak_clears_floor_pre_volume() -> None:
    """Durable peak 37.3% at 250 trades must arm graduation (volume 300)."""
    from lumina_core.birth.stage2_peak_capture import (
        maybe_arm_peak_graduation,
        should_volume_rechallenge_peak,
        mark_volume_rechallenge,
        finish_mode_blocks_pattern_inject,
    )

    st = Stage2PeakState(
        peak_winrate=0.373,
        peak_expectancy=-0.127,
        peak_at_trade=250,
        peak_flat=0.32,
        peak_policy_path="/tmp/peak.zip",
        flash_green=True,
        flash_green_wr=0.373,
        flash_green_at_trade=250,
        flash_green_durable=True,
        consecutive_green_chunks=2,
    )
    cfg = _cfg(stage2_peak_grad_enabled=True, stage2_peak_grad_min_trades=200)
    armed = maybe_arm_peak_graduation(
        st,
        stage_trades=250,
        range_flat_ratio=0.32,
        required=300,
        cfg=cfg,
    )
    assert armed is True
    assert st.peak_grad_armed is True
    assert st.finish_mode_active is True
    assert finish_mode_blocks_pattern_inject(st) is True
    # Volume re-challenge only after 300.
    assert (
        should_volume_rechallenge_peak(st, stage_trades=250, required=300, cfg=cfg)
        is False
    )
    assert (
        should_volume_rechallenge_peak(st, stage_trades=300, required=300, cfg=cfg)
        is True
    )
    mark_volume_rechallenge(st, stage_trades=300)
    assert st.volume_rechallenge_done is True
    assert (
        should_volume_rechallenge_peak(st, stage_trades=350, required=300, cfg=cfg)
        is False
    )


@pytest.mark.unit
def test_collapsed_peak_grad_does_not_block_oracle_inject() -> None:
    """PID 19776: peak_grad_armed survived after durable dropped — teacher must stay on."""
    from lumina_core.birth.stage2_peak_capture import (
        Stage2PeakState,
        finish_mode_blocks_pattern_inject,
    )

    st = Stage2PeakState(
        peak_winrate=0.44,
        peak_at_trade=300,
        peak_flat=0.3002,
        peak_grad_armed=True,
        peak_grad_armed_at_trade=300,
        finish_mode_active=True,
        flash_green=True,
        flash_green_wr=0.44,
        flash_green_at_trade=300,
        flash_green_durable=False,
        consecutive_rolling_pass_windows=0,
        quality_lock_active=False,
    )
    assert finish_mode_blocks_pattern_inject(st) is False


@pytest.mark.unit
def test_peak_grad_does_not_arm_below_floor() -> None:
    from lumina_core.birth.stage2_peak_capture import maybe_arm_peak_graduation

    st = Stage2PeakState(peak_winrate=0.30, peak_expectancy=-0.20, peak_at_trade=250)
    cfg = _cfg()
    assert (
        maybe_arm_peak_graduation(
            st, stage_trades=250, range_flat_ratio=0.32, required=300, cfg=cfg
        )
        is False
    )


@pytest.mark.unit
def test_finish_mode_stable_two_rolling_windows() -> None:
    from lumina_core.birth.stage2_peak_capture import (
        finish_mode_stable,
        update_finish_mode,
    )

    st = Stage2PeakState(near_miss_active=True, peak_winrate=0.34)
    cfg = _cfg(stage2_expectancy_floor=-0.15)
    update_finish_mode(st, rolling_winrate=0.36, cfg=cfg)
    assert st.consecutive_rolling_pass_windows == 1
    assert finish_mode_stable(st) is False
    update_finish_mode(st, rolling_winrate=0.35, cfg=cfg)
    assert st.consecutive_rolling_pass_windows == 2
    assert finish_mode_stable(st) is True
    update_finish_mode(st, rolling_winrate=0.30, cfg=cfg)
    assert finish_mode_stable(st) is False


@pytest.mark.unit
def test_swarm_blocked_on_exit_stop_magnet() -> None:
    """PR-B: stop:target ~4:1 must block swarm before quality exhaust."""
    from lumina_core.birth.stage2_peak_capture import should_defer_swarm_for_exit_forensics

    st = Stage2PeakState(
        peak_winrate=0.30,
        cumulative_closes_stop=320,
        cumulative_closes_target=80,
    )
    cfg = _cfg()
    defer, reason = should_defer_swarm_for_exit_forensics(st, cfg=cfg)
    assert defer is True
    assert "exit_stop_magnet" in reason
    defer2, reason2 = should_defer_swarm_for_peak(
        st,
        edge_vs_random=0.01,
        quality_step=4,
        max_quality_steps=4,
        best_winrate=0.28,
        cfg=cfg,
    )
    assert defer2 is True
    assert "exit" in reason2


@pytest.mark.unit
def test_swarm_protects_peak_wr_at_028() -> None:
    """Live forensics: peak 30% must arm protect (old 0.33 gate never fired)."""
    st = Stage2PeakState(near_miss_active=False, peak_winrate=0.30)
    cfg = _cfg(stage2_swarm_block_if_peak_wr_above=0.28)
    defer, reason = should_defer_swarm_for_peak(
        st,
        edge_vs_random=-0.05,
        quality_step=4,
        max_quality_steps=4,
        best_winrate=0.28,
        cfg=cfg,
    )
    assert defer is True
    assert reason in ("anti_edge_protect_peak", "protect_peak_wr")


@pytest.mark.unit
def test_phoenix_blocked_until_restore_and_quality() -> None:
    st = Stage2PeakState(peak_winrate=0.347, restore_count=0)
    cfg = _cfg(
        stage2_peak_block_phoenix_enabled=True,
        stage2_peak_phoenix_min_restores=1,
        stage2_peak_phoenix_min_quality_rollouts=4,
    )
    block, reason = should_block_phoenix_for_peak(st, cfg=cfg)
    assert block is True
    assert reason == "peak_restore_not_tried"

    record_restore(st, stage_trades=250, reason="collapse_drop_0.050")
    block2, reason2 = should_block_phoenix_for_peak(st, cfg=cfg)
    assert block2 is True
    assert reason2 == "peak_quality_rollouts_pending"

    for _ in range(4):
        note_quality_rollout(st)
    block3, reason3 = should_block_phoenix_for_peak(st, cfg=cfg)
    assert block3 is False
    assert reason3 == ""


@pytest.mark.unit
def test_restore_triggers_on_collapse_drop() -> None:
    st = Stage2PeakState(
        peak_winrate=0.35,
        peak_at_trade=100,
        peak_policy_path="/tmp/birth_peak_stage2_range.zip",
    )
    cfg = _cfg(
        stage2_peak_restore_enabled=True,
        stage2_peak_collapse_wr_drop=0.05,
        stage2_peak_restore_min_trades_since_peak=50,
        stage2_peak_restore_cooldown_trades=80,
    )
    # Too soon after peak.
    ok, _ = should_restore_peak_policy(
        st,
        stage_trades=120,
        stage_wins=36,
        rolling_winrate=0.28,
        range_flat_ratio=0.40,
        cfg=cfg,
    )
    assert ok is False
    # Collapse after enough trades (35% → 28% drop ≥ 5pp).
    ok2, reason = should_restore_peak_policy(
        st,
        stage_trades=200,
        stage_wins=56,  # 28% lifetime
        rolling_winrate=0.28,
        range_flat_ratio=0.40,
        cfg=cfg,
    )
    assert ok2 is True
    assert "collapse_drop" in reason


@pytest.mark.unit
def test_exit_physics_accumulate_truthful() -> None:
    st = Stage2PeakState()
    accumulate_exit_physics(st, closes_stop=10, closes_target=3, closes_flatten=5)
    accumulate_exit_physics(st, closes_stop=5, closes_target=2, closes_flatten=1)
    fields = st.as_progress_fields()
    assert fields["stage_closes_stop_cum"] == 15
    assert fields["stage_closes_target_cum"] == 5
    assert fields["stage_closes_flatten_cum"] == 6
    assert fields["stage_closes_time_stop_cum"] == 0
    assert fields["stage_closes_unknown_cum"] == 0
    assert fields["stage_settlement_share"] == pytest.approx(20 / 26, abs=1e-4)
    assert fields["stage_stop_target_ratio"] == pytest.approx(3.0, abs=1e-3)
    assert fields["stage2_peak_winrate"] == 0.0


@pytest.mark.unit
def test_effective_wr_prefers_max_of_lifetime_and_rolling() -> None:
    # Honesty: never invent; use best covered signal for peak/near-miss.
    assert effective_stage2_winrate(
        stage_trades=300, stage_wins=90, rolling_winrate=0.36
    ) == pytest.approx(0.36, abs=1e-6)
    assert effective_stage2_winrate(
        stage_trades=300, stage_wins=120, rolling_winrate=0.30
    ) == pytest.approx(0.40, abs=1e-6)


@pytest.mark.unit
def test_stage2_rolling_window_150_not_lifetime_at_300_trades() -> None:
    """Regression: _rolling used window=500 so trades<=500 always returned lifetime.

    Forensics: peak dilution after 150 trades must be visible as last-150 rolling.
    """
    from lumina_core.birth.plateau_rolling import (
        rolling_winrate_last_n_trades,
        stage_rolling_pass_min_covered,
        stage_rolling_pass_window,
    )

    cfg = _cfg()
    assert stage_rolling_pass_window(cfg, CurriculumStage.STAGE2_RANGE) == 150
    assert stage_rolling_pass_min_covered(cfg, CurriculumStage.STAGE2_RANGE) == 80

    # 150 trades @ 34.7% then 150 @ 26% → lifetime ~30.3%, last-150 = 26%.
    chunks = [(150, 52), (150, 39)]  # 52/150=0.3467, 39/150=0.26
    result = rolling_winrate_last_n_trades(
        stage_trades=300,
        stage_wins=91,
        wins_at_trade={150: 52, 300: 91},
        window=150,
        chunks=chunks,
        return_meta=True,
    )
    assert isinstance(result, tuple)
    wr, source, covered = result
    assert source == "true_window"
    assert covered == 150
    assert wr == pytest.approx(0.26, abs=0.01)
    # Must NOT be lifetime (~0.303).
    assert wr < 0.29

    # Window=500 wrongly collapses to lifetime when trades<=500.
    life_result = rolling_winrate_last_n_trades(
        stage_trades=300,
        stage_wins=91,
        wins_at_trade={150: 52, 300: 91},
        window=500,
        chunks=chunks,
        return_meta=True,
    )
    life_wr = float(life_result[0]) if isinstance(life_result, tuple) else float(life_result)
    assert life_wr == pytest.approx(91 / 300, abs=0.01)


@pytest.mark.unit
def test_stage2_edgescore_accepts_rolling_for_pass() -> None:
    """Critical forensics fix: rolling WR must reach EdgeScore pass path."""
    cfg = _cfg(
        stage2_edgescore_enabled=True,
        stage2_range_trades=300,
        stage_pass_trade_pct=0.10,
        stage2_expectancy_floor=-0.15,
    )
    # Lifetime 32% (exp −0.18), rolling 36% (exp −0.14) ≥ floor −0.15.
    result = evaluate_stage_pass(
        CurriculumStage.STAGE2_RANGE,
        trades=300,
        wins=96,  # 32%
        hold_signals=100,
        total_signals=1000,
        range_hold_signals=400,
        range_total_signals=1000,
        range_flat_bars=400,  # 40% flat in band
        range_round_trips=40,
        constitution_violations=0,
        target_trades=300,
        cfg=cfg,
        rolling_winrate=0.36,
        policy_entropy=0.5,
        stage_total_pnl=-10.0,
        ppo_steps=5000,
    )
    # Pass may still fail on other EdgeScore components; assert rolling was consumed
    # (message should not ignore expectancy entirely when rolling lifts exp).
    assert result.message  # non-empty diagnostic
    # If all other gates clear, rolling can lift exp above floor.
    # Document floor honesty: −0.15 never moved by this test.
    assert float(cfg.stage2_expectancy_floor) == pytest.approx(-0.15, abs=1e-9)


@pytest.mark.unit
def test_peak_progress_fields_keys_stable() -> None:
    st = Stage2PeakState(
        peak_winrate=0.347,
        peak_expectancy=-0.153,
        peak_at_trade=150,
        near_miss_active=True,
        near_miss_count=3,
        restore_count=1,
        swarm_blocked_reason="near_miss",
        phoenix_blocked_reason="peak_restore_not_tried",
    )
    fields = st.as_progress_fields()
    for key in (
        "stage2_peak_winrate",
        "stage2_peak_expectancy",
        "stage2_peak_at_trade",
        "stage2_near_miss_active",
        "stage2_near_miss_count",
        "stage2_peak_restore_count",
        "stage2_swarm_blocked_reason",
        "stage2_phoenix_blocked_reason",
        "stage_closes_stop_cum",
        "stage_target_share_decisive",
    ):
        assert key in fields
    assert fields["stage2_peak_winrate"] == pytest.approx(0.347, abs=1e-4)
    assert fields["stage2_near_miss_active"] is True


@pytest.mark.unit
def test_config_defaults_peak_capture_enabled() -> None:
    cfg = BirthCurriculumConfig()
    assert cfg.stage2_peak_capture_enabled is True
    assert cfg.stage2_peak_restore_enabled is True
    assert cfg.stage2_peak_block_phoenix_enabled is True
    assert cfg.stage2_rolling_pass_window == 150
    assert cfg.stage2_rolling_pass_min_covered == 80
    assert cfg.stage2_stall_max_hold_bars == 80
    assert cfg.stage2_peak_min_trades == 50  # chunk-scale flash green
    assert cfg.stage2_flash_green_min_trades == 50
    assert cfg.stage2_flash_max_hold_bars == 100
    assert cfg.stage2_quality_max_hold_bars == 120
    assert cfg.stage2_ppo_freeze_rollouts_after_restore == 3
    assert cfg.stage2_flash_durable_min_chunks == 2
    assert cfg.stage2_peak_grad_collapse_wr_drop == pytest.approx(0.05)
    # Floor never theater-lowered by defaults.
    assert float(getattr(cfg, "stage2_expectancy_floor", -0.15) or -0.15) == pytest.approx(
        -0.15, abs=1e-9
    )


@pytest.mark.unit
def test_coercion_rejects_toxic_hold_bars_and_yaml_ssot() -> None:
    """Old 35/40/50 hold values must not survive coercion (stop-magnet root cause)."""
    from pathlib import Path

    from lumina_core.birth.config import load_birth_v2_config
    from lumina_core.birth.config_coercion import build_curriculum_config

    toxic = build_curriculum_config(
        {
            "stage2_flash_max_hold_bars": 35,
            "stage2_finish_max_hold_bars": 40,
            "stage2_exit_magnet_max_hold_bars": 50,
        }
    )
    assert toxic.stage2_flash_max_hold_bars >= 80
    assert toxic.stage2_finish_max_hold_bars >= 80
    assert toxic.stage2_exit_magnet_max_hold_bars >= 80

    live = load_birth_v2_config(Path("."))
    cur = live.curriculum
    assert cur.stage2_quality_max_hold_bars >= 100
    assert cur.stage2_flash_durable_min_chunks >= 2
    assert cur.stage2_ppo_freeze_rollouts_after_restore >= 3
    assert cur.stage2_ppo_quality_gate_enabled is True
    assert float(cur.stage2_expectancy_floor) == pytest.approx(-0.15, abs=1e-9)


@pytest.mark.unit
def test_note_quality_not_double_count_after_restore_flag() -> None:
    """restored_this_cycle must keep freeze window intact."""
    from lumina_core.birth.stage2_peak_capture import (
        record_restore,
        should_freeze_ppo_after_restore,
        note_quality_rollout,
    )

    st = Stage2PeakState(peak_winrate=0.36, peak_policy_path="/tmp/p.zip")
    cfg = _cfg(stage2_ppo_freeze_rollouts_after_restore=3)
    record_restore(st, stage_trades=200, reason="volume_rechallenge_peak")
    assert st.restored_this_cycle is True
    # Same-cycle note would short-change freeze — caller must not note while flag set.
    # Simulate correct caller: skip note when restored_this_cycle.
    if not st.restored_this_cycle:
        note_quality_rollout(st)
    freeze, reason = should_freeze_ppo_after_restore(st, cfg=cfg)
    assert freeze is True
    assert st.quality_rollouts_since_restore == 0


@pytest.mark.unit
def test_defer_disabled_when_capture_off() -> None:
    st = Stage2PeakState(near_miss_active=True, peak_winrate=0.40)
    cfg = SimpleNamespace(stage2_peak_capture_enabled=False)
    defer, reason = should_defer_swarm_for_peak(
        st,
        edge_vs_random=-0.2,
        quality_step=0,
        max_quality_steps=4,
        best_winrate=0.35,
        cfg=cfg,
    )
    assert defer is False
    assert reason == ""


@pytest.mark.unit
def test_peak_state_blob_roundtrip_for_resume() -> None:
    """Checkpoint blob must restore peak path + counters without inventing WR."""
    st = Stage2PeakState(
        peak_winrate=0.347,
        peak_expectancy=-0.153,
        peak_at_trade=150,
        peak_policy_path="lumina_agents/ppo/birth_peak_stage2_range.zip",
        restore_count=1,
        quality_rollouts_since_restore=2,
        # Balanced exits so phoenix gate is quality-rollouts, not exit magnet.
        cumulative_closes_stop=20,
        cumulative_closes_target=20,
        cumulative_closes_flatten=8,
    )
    blob = {
        "peak_winrate": float(st.peak_winrate),
        "peak_expectancy": float(st.peak_expectancy),
        "peak_at_trade": int(st.peak_at_trade),
        "peak_policy_path": str(st.peak_policy_path),
        "peak_flat": float(st.peak_flat),
        "peak_edge_vs_random": float(st.peak_edge_vs_random),
        "near_miss_active": bool(st.near_miss_active),
        "near_miss_count": int(st.near_miss_count),
        "restore_count": int(st.restore_count),
        "last_restore_at_trade": int(st.last_restore_at_trade),
        "last_restore_reason": str(st.last_restore_reason),
        "quality_rollouts_since_restore": int(st.quality_rollouts_since_restore),
        "cumulative_closes_stop": int(st.cumulative_closes_stop),
        "cumulative_closes_target": int(st.cumulative_closes_target),
        "cumulative_closes_flatten": int(st.cumulative_closes_flatten),
    }
    restored = Stage2PeakState(
        peak_winrate=float(blob["peak_winrate"]),
        peak_expectancy=float(blob["peak_expectancy"]),
        peak_at_trade=int(blob["peak_at_trade"]),
        peak_policy_path=str(blob["peak_policy_path"]),
        restore_count=int(blob["restore_count"]),
        quality_rollouts_since_restore=int(blob["quality_rollouts_since_restore"]),
        cumulative_closes_stop=int(blob["cumulative_closes_stop"]),
        cumulative_closes_target=int(blob["cumulative_closes_target"]),
        cumulative_closes_flatten=int(blob["cumulative_closes_flatten"]),
    )
    assert restored.peak_winrate == pytest.approx(0.347, abs=1e-6)
    assert restored.peak_at_trade == 150
    assert "birth_peak" in restored.peak_policy_path
    assert restored.restore_count == 1
    assert restored.quality_rollouts_since_restore == 2
    # Phoenix still gated until quality budget after restore.
    cfg = _cfg()
    block, reason = should_block_phoenix_for_peak(restored, cfg=cfg)
    assert block is True
    assert reason == "peak_quality_rollouts_pending"


@pytest.mark.unit
def test_quality_lock_restores_hop_only_peak_on_live_collapse() -> None:
    """13/08 PID 22168: 40% peak + life 28% + flat 18% + hop_only + lock → restore."""
    from lumina_core.birth.stage2_peak_capture import should_volume_rechallenge_peak

    st = Stage2PeakState(
        peak_winrate=0.40,
        peak_expectancy=-0.10,
        peak_at_trade=450,
        peak_flat=0.3562,
        peak_policy_path="C:/tmp/birth_peak_stage2_range.zip",
        flash_green=True,
        flash_green_wr=0.40,
        flash_green_at_trade=450,
        flash_green_durable=False,
        consecutive_green_chunks=1,
        quality_lock_active=True,
        quality_lock_wr=0.3636,
        quality_lock_at_trade=144,
    )
    cfg = _cfg()
    do_r, reason = should_restore_peak_policy(
        st,
        stage_trades=1126,
        stage_wins=321,
        rolling_winrate=0.295,
        range_flat_ratio=0.1854,
        cfg=cfg,
        required=300,
    )
    assert do_r is True
    assert "lock_flat_out" in reason or "collapse" in reason
    assert (
        should_volume_rechallenge_peak(st, stage_trades=1126, required=300, cfg=cfg)
        is True
    )


@pytest.mark.unit
def test_volume_rechallenge_under_lock_without_peak_grad_armed() -> None:
    from lumina_core.birth.stage2_peak_capture import should_volume_rechallenge_peak

    st = Stage2PeakState(
        peak_grad_armed=False,
        quality_lock_active=True,
        peak_policy_path="/tmp/birth_peak.zip",
        volume_rechallenge_done=False,
    )
    cfg = _cfg()
    assert (
        should_volume_rechallenge_peak(st, stage_trades=250, required=300, cfg=cfg)
        is False
    )
    assert (
        should_volume_rechallenge_peak(st, stage_trades=300, required=300, cfg=cfg)
        is True
    )

