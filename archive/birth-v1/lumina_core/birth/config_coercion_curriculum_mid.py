"""Stage gates / starship / survival / meta fields. (M5 curriculum coercion extract)."""
from __future__ import annotations

from typing import Any

from lumina_core.birth.config_coercion_helpers import (
    _coerce_float,
    _coerce_int,
)


def curriculum_kwargs(cur_raw: dict[str, Any]) -> dict[str, Any]:
    return dict(
        meta_explore_decay_improving=max(
            0.4,
            min(1.0, _coerce_float(cur_raw.get("meta_explore_decay_improving"), 0.65)),
        ),
        meta_explore_decay_stall=max(
            0.4,
            min(1.0, _coerce_float(cur_raw.get("meta_explore_decay_stall"), 0.50)),
        ),
        meta_intra_ramp_on_improving=bool(cur_raw.get("meta_intra_ramp_on_improving", True)),
        meta_self_eval_enabled=bool(cur_raw.get("meta_self_eval_enabled", True)),
        meta_self_eval_min_stall_attempts=max(
            5, _coerce_int(cur_raw.get("meta_self_eval_min_stall_attempts"), 32)
        ),
        meta_self_eval_min_recovery_attempts=max(
            1, _coerce_int(cur_raw.get("meta_self_eval_min_recovery_attempts"), 8)
        ),
        meta_self_eval_rollouts_per_strategy=max(
            5, min(30, _coerce_int(cur_raw.get("meta_self_eval_rollouts_per_strategy"), 12))
        ),
        meta_self_eval_min_velocity_gain=max(
            0.0, _coerce_float(cur_raw.get("meta_self_eval_min_velocity_gain"), 0.003)
        ),
        meta_self_eval_velocity_floor=max(
            0.0, _coerce_float(cur_raw.get("meta_self_eval_velocity_floor"), 0.002)
        ),
        meta_self_eval_cooldown_rollouts=max(
            0, _coerce_int(cur_raw.get("meta_self_eval_cooldown_rollouts"), 20)
        ),
        plateau_detection_enabled=bool(cur_raw.get("plateau_detection_enabled", True)),
        plateau_winrate_gap=max(0.01, _coerce_float(cur_raw.get("plateau_winrate_gap"), 0.10)),
        plateau_trades_beyond_gate_multiplier=max(
            1, _coerce_int(cur_raw.get("plateau_trades_beyond_gate_multiplier"), 3)
        ),
        plateau_min_stage_trades_pct=max(
            0.05,
            min(1.0, _coerce_float(cur_raw.get("plateau_min_stage_trades_pct"), 0.25)),
        ),
        plateau_quarantine_rollouts=max(
            1, _coerce_int(cur_raw.get("plateau_quarantine_rollouts"), 32)
        ),
        plateau_quarantine_min_trades=max(
            50, _coerce_int(cur_raw.get("plateau_quarantine_min_trades"), 500)
        ),
        plateau_evolution_min_ppo_steps_between_steps=max(
            0,
            _coerce_int(cur_raw.get("plateau_evolution_min_ppo_steps_between_steps"), 50_000),
        ),
        plateau_evolution_max_noops_per_step=max(
            1, _coerce_int(cur_raw.get("plateau_evolution_max_noops_per_step"), 3)
        ),
        plateau_max_wall_sec=max(300, _coerce_int(cur_raw.get("plateau_max_wall_sec"), 7200)),
        beyond_gate_plateau_wall_sec=max(
            120, _coerce_int(cur_raw.get("beyond_gate_plateau_wall_sec"), 900)
        ),
        plateau_max_evolution_steps=max(
            1, min(12, _coerce_int(cur_raw.get("plateau_max_evolution_steps"), 8))
        ),
        plateau_evolution_rollouts_per_step=max(
            1, _coerce_int(cur_raw.get("plateau_evolution_rollouts_per_step"), 12)
        ),
        plateau_evolution_max_rollouts_per_step=max(
            1, _coerce_int(cur_raw.get("plateau_evolution_max_rollouts_per_step"), 24)
        ),
        plateau_evolution_meaningful_delta=max(
            0.001, _coerce_float(cur_raw.get("plateau_evolution_meaningful_delta"), 0.01)
        ),
        beyond_gate_evolution_rollouts_per_step=max(
            1, _coerce_int(cur_raw.get("beyond_gate_evolution_rollouts_per_step"), 4)
        ),
        max_forced_recoveries_per_plateau=max(
            1, _coerce_int(cur_raw.get("max_forced_recoveries_per_plateau"), 12)
        ),
        max_adaptation_stuck_escapes=max(
            1, _coerce_int(cur_raw.get("max_adaptation_stuck_escapes"), 3)
        ),
        adaptation_stuck_min_rollouts=max(
            1, min(20, _coerce_int(cur_raw.get("adaptation_stuck_min_rollouts"), 5))
        ),
        policy_swarm_enabled=bool(cur_raw.get("policy_swarm_enabled", True)),
        policy_swarm_variants=max(
            2, min(5, _coerce_int(cur_raw.get("policy_swarm_variants"), 3))
        ),
        policy_swarm_rollouts_per_variant=max(
            1, _coerce_int(cur_raw.get("policy_swarm_rollouts_per_variant"), 4)
        ),
        policy_swarm_min_trades=max(
            1, _coerce_int(cur_raw.get("policy_swarm_min_trades"), 20)
        ),
        oos_proxy_enabled=bool(cur_raw.get("oos_proxy_enabled", True)),
        oos_proxy_interval_trades=max(
            100, _coerce_int(cur_raw.get("oos_proxy_interval_trades"), 500)
        ),
        oos_proxy_sample_trades=max(
            20, _coerce_int(cur_raw.get("oos_proxy_sample_trades"), 50)
        ),
        oos_proxy_weight=max(
            0.0, min(1.0, _coerce_float(cur_raw.get("oos_proxy_weight"), 0.4))
        ),
        graduation_mode=str(cur_raw.get("graduation_mode", "evolution_deferred")).strip().lower(),
        provisional_oos_floor=max(
            0.20, min(0.50, _coerce_float(cur_raw.get("provisional_oos_floor"), 0.35))
        ),
        plateau_save_best_policy=bool(cur_raw.get("plateau_save_best_policy", True)),
        plateau_best_policy_min_trades=max(
            50, _coerce_int(cur_raw.get("plateau_best_policy_min_trades"), 200)
        ),
        stage1_winrate_pass_threshold=max(
            0.20,
            min(0.60, _coerce_float(cur_raw.get("stage1_winrate_pass_threshold"), 0.45)),
        ),
        stage1_winrate_pass_floor=max(
            0.20,
            min(0.50, _coerce_float(cur_raw.get("stage1_winrate_pass_floor"), 0.35)),
        ),
        stage1_winrate_recommended=max(
            0.20,
            min(0.60, _coerce_float(cur_raw.get("stage1_winrate_recommended"), 0.45)),
        ),
        stage1_use_rolling_pass=bool(cur_raw.get("stage1_use_rolling_pass", True)),
        stage1_rolling_pass_window=max(
            100, _coerce_int(cur_raw.get("stage1_rolling_pass_window"), 500)
        ),
        stage1_edgescore_enabled=bool(cur_raw.get("stage1_edgescore_enabled", True)),
        stage1_entropy_floor=max(
            0.0, min(2.0, _coerce_float(cur_raw.get("stage1_entropy_floor"), 0.05))
        ),
        stage1_hold_ratio_min=max(
            0.0, min(0.50, _coerce_float(cur_raw.get("stage1_hold_ratio_min"), 0.05))
        ),
        stage1_hold_ratio_max=max(
            0.50, min(0.99, _coerce_float(cur_raw.get("stage1_hold_ratio_max"), 0.85))
        ),
        stage1_expectancy_floor=_coerce_float(cur_raw.get("stage1_expectancy_floor"), -0.15),
        stage2_expectancy_floor=_coerce_float(
            cur_raw.get("stage2_expectancy_floor"),
            _coerce_float(cur_raw.get("stage1_expectancy_floor"), -0.15),
        ),
        stage2_expectancy_quality_max_steps=max(
            1, min(12, _coerce_int(cur_raw.get("stage2_expectancy_quality_max_steps"), 4))
        ),
        stage2_expectancy_swarm_defer_steps=max(
            0, min(8, _coerce_int(cur_raw.get("stage2_expectancy_swarm_defer_steps"), 2))
        ),
        stage2_cold_bootstrap_policy=bool(
            cur_raw.get("stage2_cold_bootstrap_policy", True)
        ),
        stage2_oracle_bootstrap_steps=max(
            0,
            min(50_000, _coerce_int(cur_raw.get("stage2_oracle_bootstrap_steps"), 5000)),
        ),
        stage2_min_net_oracle_pnl=max(
            0.0,
            min(50.0, _coerce_float(cur_raw.get("stage2_min_net_oracle_pnl"), 0.50)),
        ),
        stage2_reinit_action_head=bool(cur_raw.get("stage2_reinit_action_head", True)),
        stage2_bootstrap_min_buffer_reward=_coerce_float(
            cur_raw.get("stage2_bootstrap_min_buffer_reward"), 0.0
        ),
        stage2_bootstrap_max_buffer=max(
            200, min(50_000, _coerce_int(cur_raw.get("stage2_bootstrap_max_buffer"), 4000))
        ),
        stage2_skill_metric_policy_only=bool(
            cur_raw.get("stage2_skill_metric_policy_only", True)
        ),
        stage2_skill_min_trades=max(
            20, min(2000, _coerce_int(cur_raw.get("stage2_skill_min_trades"), 150))
        ),
        stage2_rolling_pass_window=max(
            50, min(1000, _coerce_int(cur_raw.get("stage2_rolling_pass_window"), 150))
        ),
        stage2_rolling_pass_min_covered=max(
            40, min(500, _coerce_int(cur_raw.get("stage2_rolling_pass_min_covered"), 80))
        ),
        stage2_peak_capture_enabled=bool(cur_raw.get("stage2_peak_capture_enabled", True)),
        stage2_peak_min_trades=max(
            40, min(500, _coerce_int(cur_raw.get("stage2_peak_min_trades"), 50))
        ),
        stage2_flash_green_min_trades=max(
            40, min(200, _coerce_int(cur_raw.get("stage2_flash_green_min_trades"), 50))
        ),
        stage2_flash_durable_min_chunks=max(
            2, min(5, _coerce_int(cur_raw.get("stage2_flash_durable_min_chunks"), 2))
        ),
        # Floor 80: old 35-bar thrash recreated stop-magnet (forensics 2026-08-12).
        stage2_flash_max_hold_bars=max(
            80, min(180, _coerce_int(cur_raw.get("stage2_flash_max_hold_bars"), 100))
        ),
        stage2_near_miss_exp_delta=max(
            0.005, min(0.08, _coerce_float(cur_raw.get("stage2_near_miss_exp_delta"), 0.02))
        ),
        stage2_peak_restore_enabled=bool(cur_raw.get("stage2_peak_restore_enabled", True)),
        stage2_peak_collapse_wr_drop=max(
            0.02, min(0.20, _coerce_float(cur_raw.get("stage2_peak_collapse_wr_drop"), 0.05))
        ),
        stage2_peak_restore_min_trades_since_peak=max(
            20,
            min(
                500,
                _coerce_int(cur_raw.get("stage2_peak_restore_min_trades_since_peak"), 50),
            ),
        ),
        stage2_peak_restore_cooldown_trades=max(
            20,
            min(500, _coerce_int(cur_raw.get("stage2_peak_restore_cooldown_trades"), 80)),
        ),
        stage2_peak_block_phoenix_enabled=bool(
            cur_raw.get("stage2_peak_block_phoenix_enabled", True)
        ),
        stage2_peak_phoenix_min_restores=max(
            0, min(5, _coerce_int(cur_raw.get("stage2_peak_phoenix_min_restores"), 1))
        ),
        stage2_peak_phoenix_min_quality_rollouts=max(
            0,
            min(20, _coerce_int(cur_raw.get("stage2_peak_phoenix_min_quality_rollouts"), 4)),
        ),
        stage2_swarm_block_if_peak_wr_above=max(
            0.25,
            min(0.45, _coerce_float(cur_raw.get("stage2_swarm_block_if_peak_wr_above"), 0.28)),
        ),
        stage2_exit_forensics_block_swarm=bool(
            cur_raw.get("stage2_exit_forensics_block_swarm", True)
        ),
        stage2_exit_forensics_stop_target_max=max(
            1.5,
            min(5.0, _coerce_float(cur_raw.get("stage2_exit_forensics_stop_target_max"), 2.5)),
        ),
        stage2_exit_forensics_target_share_min=max(
            0.15,
            min(0.50, _coerce_float(cur_raw.get("stage2_exit_forensics_target_share_min"), 0.30)),
        ),
        stage2_exit_forensics_min_decisive=max(
            10, min(200, _coerce_int(cur_raw.get("stage2_exit_forensics_min_decisive"), 40))
        ),
        stage2_quality_inject_max_patterns=max(
            50, min(2000, _coerce_int(cur_raw.get("stage2_quality_inject_max_patterns"), 200))
        ),
        stage2_peak_inject_max_patterns=max(
            30, min(1000, _coerce_int(cur_raw.get("stage2_peak_inject_max_patterns"), 120))
        ),
        stage2_beat_random_inject_max_patterns=max(
            20, min(500, _coerce_int(cur_raw.get("stage2_beat_random_inject_max_patterns"), 80))
        ),
        stage2_stall_max_hold_bars=max(
            20, min(180, _coerce_int(cur_raw.get("stage2_stall_max_hold_bars"), 80))
        ),
        stage2_quality_max_hold_bars=max(
            60, min(180, _coerce_int(cur_raw.get("stage2_quality_max_hold_bars"), 120))
        ),
        # Floor 80: magnet clamp must not re-introduce early FORCE_EXIT thrash.
        stage2_exit_magnet_max_hold_bars=max(
            80, min(180, _coerce_int(cur_raw.get("stage2_exit_magnet_max_hold_bars"), 80))
        ),
        stage2_exit_magnet_stop_target_ratio=max(
            1.5,
            min(5.0, _coerce_float(cur_raw.get("stage2_exit_magnet_stop_target_ratio"), 2.5)),
        ),
        stage2_force_exit_on_expectancy_gap=bool(
            cur_raw.get("stage2_force_exit_on_expectancy_gap", False)
        ),
        stage2_early_quality_freeze_enabled=bool(
            cur_raw.get("stage2_early_quality_freeze_enabled", True)
        ),
        stage2_early_quality_wall_cooldown_sec=max(
            30.0,
            min(1800.0, _coerce_float(cur_raw.get("stage2_early_quality_wall_cooldown_sec"), 300.0)),
        ),
        stage2_peak_grad_enabled=bool(cur_raw.get("stage2_peak_grad_enabled", True)),
        stage2_peak_grad_min_trades=max(
            80, min(500, _coerce_int(cur_raw.get("stage2_peak_grad_min_trades"), 200))
        ),
        stage2_peak_grad_collapse_wr_drop=max(
            0.03,
            min(0.15, _coerce_float(cur_raw.get("stage2_peak_grad_collapse_wr_drop"), 0.05)),
        ),
        stage2_finish_max_hold_bars=max(
            80, min(180, _coerce_int(cur_raw.get("stage2_finish_max_hold_bars"), 100))
        ),
        stage2_ppo_freeze_after_restore_enabled=bool(
            cur_raw.get("stage2_ppo_freeze_after_restore_enabled", True)
        ),
        stage2_ppo_freeze_rollouts_after_restore=max(
            1,
            min(10, _coerce_int(cur_raw.get("stage2_ppo_freeze_rollouts_after_restore"), 3)),
        ),
        stage2_ppo_freeze_trades_after_restore=max(
            40,
            min(400, _coerce_int(cur_raw.get("stage2_ppo_freeze_trades_after_restore"), 120)),
        ),
        stage2_ppo_quality_gate_enabled=bool(
            cur_raw.get("stage2_ppo_quality_gate_enabled", True)
        ),
        stage2_ppo_quality_min_chunk_wr=max(
            0.20,
            min(0.40, _coerce_float(cur_raw.get("stage2_ppo_quality_min_chunk_wr"), 0.26)),
        ),
        stage2_quality_lock_enabled=bool(
            cur_raw.get("stage2_quality_lock_enabled", True)
        ),
        stage2_quality_lock_chunk_wr=max(
            0.30,
            min(0.50, _coerce_float(cur_raw.get("stage2_quality_lock_chunk_wr"), 0.36)),
        ),
        stage2_quality_lock_exp_floor=max(
            -0.20,
            min(-0.05, _coerce_float(cur_raw.get("stage2_quality_lock_exp_floor"), -0.14)),
        ),
        stage2_pass_durable_enabled=bool(cur_raw.get("stage2_pass_durable_enabled", True)),
        stage2_pass_rolling_streak=max(
            1, min(5, _coerce_int(cur_raw.get("stage2_pass_rolling_streak"), 2))
        ),
        stage2_pass_lifetime_delta=max(
            0.0, min(0.15, _coerce_float(cur_raw.get("stage2_pass_lifetime_delta"), 0.05))
        ),
        stage2_transfer_handoff_enabled=bool(
            cur_raw.get("stage2_transfer_handoff_enabled", True)
        ),
        stage2_transfer_purge_buffer=bool(cur_raw.get("stage2_transfer_purge_buffer", True)),
        stage2_transfer_keep_buffer_top_pct=max(
            0.0,
            min(0.5, _coerce_float(cur_raw.get("stage2_transfer_keep_buffer_top_pct"), 0.10)),
        ),
        stage2_transfer_max_buffer_keep=max(
            0, min(20_000, _coerce_int(cur_raw.get("stage2_transfer_max_buffer_keep"), 500))
        ),
        stage2_transfer_reinit_action_head=bool(
            cur_raw.get("stage2_transfer_reinit_action_head", True)
        ),
        stage2_transfer_reinit_below_wr=max(
            0.20,
            min(0.45, _coerce_float(cur_raw.get("stage2_transfer_reinit_below_wr"), 0.32)),
        ),
        stage3_pass_durable_enabled=bool(
            cur_raw.get("stage3_pass_durable_enabled", True)
        ),
        stage3_pass_rolling_streak=max(
            1, min(5, _coerce_int(cur_raw.get("stage3_pass_rolling_streak"), 2))
        ),
        stage3_pass_lifetime_delta=max(
            0.0, min(0.15, _coerce_float(cur_raw.get("stage3_pass_lifetime_delta"), 0.05))
        ),
        stage3_occupancy_pass_enabled=bool(
            cur_raw.get("stage3_occupancy_pass_enabled", True)
        ),
        stage3_position_flat_min=max(
            0.15, min(0.45, _coerce_float(cur_raw.get("stage3_position_flat_min"), 0.25))
        ),
        stage3_position_flat_max=max(
            0.50, min(0.90, _coerce_float(cur_raw.get("stage3_position_flat_max"), 0.75))
        ),
        stage3_occupancy_all_ticks=bool(cur_raw.get("stage3_occupancy_all_ticks", True)),
        settlement_honesty_enabled=bool(cur_raw.get("settlement_honesty_enabled", True)),
        settlement_min_decisive_share=max(
            0.50,
            min(0.95, _coerce_float(cur_raw.get("settlement_min_decisive_share"), 0.70)),
        ),
        stage3_participation_envelope_enabled=bool(
            cur_raw.get("stage3_participation_envelope_enabled", True)
        ),
        stage3_participation_min_signals=max(
            20, min(200, _coerce_int(cur_raw.get("stage3_participation_min_signals"), 50))
        ),
        stage3_participation_min_dwell_bars=max(
            2, min(40, _coerce_int(cur_raw.get("stage3_participation_min_dwell_bars"), 8))
        ),
        stage3_participation_band_lo=max(
            0.15, min(0.50, _coerce_float(cur_raw.get("stage3_participation_band_lo"), 0.28))
        ),
        stage3_participation_band_hi=max(
            0.40, min(0.90, _coerce_float(cur_raw.get("stage3_participation_band_hi"), 0.72))
        ),
        stage3_participation_hysteresis=max(
            0.0,
            min(0.08, _coerce_float(cur_raw.get("stage3_participation_hysteresis"), 0.0)),
        ),
        stage3_participation_under_band_release_hysteresis=max(
            0.0,
            min(
                0.08,
                _coerce_float(
                    cur_raw.get("stage3_participation_under_band_release_hysteresis"), 0.0
                ),
            ),
        ),
        stage3_occupancy_control_window_bars=max(
            50,
            min(
                5000,
                _coerce_int(cur_raw.get("stage3_occupancy_control_window_bars"), 500),
            ),
        ),
        birth_twin_freeze_resolve_enabled=bool(
            cur_raw.get("birth_twin_freeze_resolve_enabled", True)
        ),
        birth_survival_pass_enabled=bool(cur_raw.get("birth_survival_pass_enabled", True)),
        birth_survival_wr_floor=max(
            0.05, min(0.45, _coerce_float(cur_raw.get("birth_survival_wr_floor"), 0.20))
        ),
        birth_survival_expectancy_floor=_coerce_float(
            cur_raw.get("birth_survival_expectancy_floor"), -0.50
        ),
        birth_plant_soft_block_rate_max_per_1k=max(
            1.0,
            _coerce_float(cur_raw.get("birth_plant_soft_block_rate_max_per_1k"), 100.0),
        ),
        stage1_foundation_pressure_enabled=bool(
            cur_raw.get("stage1_foundation_pressure_enabled", True)
        ),
        stage1_foundation_target_wr=max(
            0.22,
            min(0.45, _coerce_float(cur_raw.get("stage1_foundation_target_wr"), 0.30)),
        ),
        stage1_anti_thrash_wr=max(
            0.20,
            min(0.40, _coerce_float(cur_raw.get("stage1_anti_thrash_wr"), 0.25)),
        ),
        stage1_transfer_handoff_enabled=bool(
            cur_raw.get("stage1_transfer_handoff_enabled", True)
        ),
        stage1_transfer_purge_buffer=bool(
            cur_raw.get("stage1_transfer_purge_buffer", True)
        ),
        stage1_transfer_keep_buffer_top_pct=max(
            0.0,
            min(
                0.50,
                _coerce_float(cur_raw.get("stage1_transfer_keep_buffer_top_pct"), 0.0),
            ),
        ),
        stage1_transfer_max_buffer_keep=max(
            0, min(20_000, _coerce_int(cur_raw.get("stage1_transfer_max_buffer_keep"), 0))
        ),
        stage1_transfer_reinit_action_head=bool(
            cur_raw.get("stage1_transfer_reinit_action_head", True)
        ),
        starship_entropy_life_support_enabled=bool(
            cur_raw.get("starship_entropy_life_support_enabled", True)
        ),
        starship_swarm_first_enabled=bool(cur_raw.get("starship_swarm_first_enabled", True)),
        starship_exploration_burst_multiplier=max(
            1.0,
            min(8.0, _coerce_float(cur_raw.get("starship_exploration_burst_multiplier"), 2.5)),
        ),
        starship_certified_plateau_max_evolution_steps=max(
            1,
            min(
                12,
                _coerce_int(cur_raw.get("starship_certified_plateau_max_evolution_steps"), 4),
            ),
        ),
        starship_stall_after_swarm_only=bool(
            cur_raw.get("starship_stall_after_swarm_only", True)
        ),
        starship_champion_freeze_enabled=bool(
            cur_raw.get("starship_champion_freeze_enabled", True)
        ),
        starship_champion_edgescore_gap=max(
            0.001,
            min(0.20, _coerce_float(cur_raw.get("starship_champion_edgescore_gap"), 0.02)),
        ),
        starship_entropy_required_after_ppo_steps=max(
            0, _coerce_int(cur_raw.get("starship_entropy_required_after_ppo_steps"), 500)
        ),
        starship_twin_continue_when_full_auto=bool(
            cur_raw.get("starship_twin_continue_when_full_auto", True)
        ),
        stage2_edgescore_enabled=bool(cur_raw.get("stage2_edgescore_enabled", True)),
    )


__all__ = ["curriculum_kwargs"]
