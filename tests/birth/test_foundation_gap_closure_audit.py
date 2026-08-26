"""Contract audit: no open gaps in Stage1 foundation / Stage2 multi-blocker path."""

from __future__ import annotations

from pathlib import Path


def _read(rel: str) -> str:
    return Path(rel).read_text(encoding="utf-8")


def test_stage1_handoff_on_graduation() -> None:
    src = _read("lumina_core/birth/engine_graduation.py")
    assert "execute_stage1_transfer_handoff" in src
    assert "write_birth_progress" in src
    assert "stage1_transfer_handoff_ok" in src


def test_stage2_handoff_on_graduation() -> None:
    src = _read("lumina_core/birth/engine_graduation.py")
    assert "execute_stage2_transfer_handoff" in src
    handoff = _read("lumina_core/birth/stage2_transfer_handoff.py")
    assert "keep_pct = min(keep_pct, 0.05)" in handoff


def test_stage1_foundation_meta_all_triggers() -> None:
    assert "stage1_foundation" in _read("lumina_core/birth/meta_decide_after_rollout.py")
    assert "stage1_foundation" in _read("lumina_core/birth/meta_decide_pre_rollout.py")
    assert "stage1_foundation" in _read("lumina_core/birth/meta_decide_periodic.py")
    assert "_stage1_foundation_gap" in _read(
        "lumina_core/birth/stage_loop_rollout_pre_caps.py"
    )


def test_stage2_skill_wired_everywhere() -> None:
    assert "policy_trades" in _read("lumina_core/birth/stage_loop_progress_write.py")
    assert "policy_trades" in _read("lumina_core/birth/plateau_evolution_detect.py")
    assert "policy_trades" in _read("lumina_core/birth/stage_loop_recovery_terminal.py")
    assert "policy_trades" in _read("lumina_core/birth/wall_trigger_engine.py")
    assert "policy_trades" in _read("lumina_core/birth/wall_adaptation_triggers.py")
    assert "policy_trades" in _read("lumina_core/birth/stage_pass_receipt_verify.py")
    assert "policy_trades" in _read("lumina_core/birth/stage_pass_receipt_types.py")


def test_no_zero_policy_trades_collapsed_to_none() -> None:
    """policy_trades=0 must not become None (would grade plant as pilot)."""
    bad = 'stage_policy_trades", 0) or 0) or None'
    for rel in (
        "lumina_core/birth/stage_loop_iteration_pass.py",
        "lumina_core/birth/stage_loop_progress_write.py",
        "lumina_core/birth/stage_loop_data_enrich_core.py",
        "lumina_core/birth/plateau_evolution_detect.py",
        "lumina_core/birth/stage_loop_recovery_terminal.py",
    ):
        assert bad not in _read(rel), rel


def test_stage2_bootstrap_and_pass_vector() -> None:
    assert "run_stage2_cold_bootstrap" in _read(
        "lumina_core/birth/stage_loop_session_phase_prepare_init.py"
    )
    assert "plan_stage2_from_snapshot" in _read(
        "lumina_core/birth/meta_decide_after_rollout.py"
    )
    assert "plan_stage2_from_snapshot" in _read(
        "lumina_core/birth/meta_decide_periodic.py"
    )


def test_under_band_dead_zone_and_force_exit_wired() -> None:
    env = _read("lumina_core/birth/stage2_participation_envelope.py")
    assert "under_band_release" in env or "under_band_enter" in env
    assert "FORCE_EXIT" in env or "MODE_FORCE_EXIT" in env
    assert "max_hold" in env
    sim = _read("lumina_core/birth/sim_runner.py")
    assert "force_flatten_this_step" in sim
    assert "force_time_stop_this_step" in sim
    assert "MODE_FORCE_EXIT" in sim
    gym = _read("lumina_core/rl/gym_environment_step.py")
    assert "force_flatten_this_step" in gym
    assert "force_time_stop_this_step" in gym
    assert "time_stop" in gym
    assert "force_exit" in gym


def test_survival_floor_unchanged() -> None:
    from lumina_core.birth.config import BirthCurriculumConfig

    c = BirthCurriculumConfig()
    assert c.birth_survival_wr_floor == 0.20
    assert c.birth_survival_expectancy_floor == -0.50
    assert c.stage2_expectancy_floor == -0.15
    assert c.stage1_foundation_target_wr == 0.30
    assert c.stage1_transfer_handoff_enabled is True
    assert c.stage2_skill_metric_policy_only is True
