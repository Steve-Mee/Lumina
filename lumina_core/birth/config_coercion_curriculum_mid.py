"""Stage gates / starship / survival / meta fields. (M5 curriculum coercion extract)."""
from __future__ import annotations

from typing import Any

from lumina_core.birth.config_coercion_helpers import (
    _coerce_float,
    _coerce_int,
    _coerce_wall_behavior,
    _parse_expansion_steps,
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
