"""Stage/rollout/oracle/adaptation/plateau fields. (M5 curriculum coercion extract)."""
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
        stage1_trend_trades=_coerce_int(cur_raw.get("stage1_trend_trades"), 2000),
        stage2_range_trades=_coerce_int(cur_raw.get("stage2_range_trades"), 3000),
        stage3_mixed_trades=_coerce_int(cur_raw.get("stage3_mixed_trades"), 5000),
        stage_pass_trade_pct=max(
            0.05,
            min(1.0, _coerce_float(cur_raw.get("stage_pass_trade_pct"), 0.10)),
        ),
        stage_pass_min_trades=max(50, _coerce_int(cur_raw.get("stage_pass_min_trades"), 100)),
        stage4_polish_ppo_steps=_coerce_int(cur_raw.get("stage4_polish_ppo_steps"), 50_000),
        rollout_step_budget_multiplier=_coerce_int(cur_raw.get("rollout_step_budget_multiplier"), 40),
        stall_probe_steps=_coerce_int(cur_raw.get("stall_probe_steps"), 5000),
        exploration_steps=_coerce_int(cur_raw.get("exploration_steps"), 2000),
        rollout_chunk_trades=_coerce_int(cur_raw.get("rollout_chunk_trades"), 250),
        max_rollouts_per_stage=_coerce_int(cur_raw.get("max_rollouts_per_stage"), 500),
        max_escalation_level=_coerce_int(cur_raw.get("max_escalation_level"), 5),
        gen0_provisional_min_trades=_coerce_int(cur_raw.get("gen0_provisional_min_trades"), 25),
        oracle_scan_stride=_coerce_int(cur_raw.get("oracle_scan_stride"), 5),
        oracle_patterns_per_stage=_coerce_int(cur_raw.get("oracle_patterns_per_stage"), 5000),
        oracle_max_hold_bars=_coerce_int(cur_raw.get("oracle_max_hold_bars"), 120),
        data_expansion_steps=_parse_expansion_steps(cur_raw.get("data_expansion_steps")),
        stagnation_rollouts_before_expand=_coerce_int(cur_raw.get("stagnation_rollouts_before_expand"), 5),
        curriculum_ppo_timesteps=_coerce_int(cur_raw.get("curriculum_ppo_timesteps"), 3_000),
        polish_ppo_timesteps=_coerce_int(cur_raw.get("polish_ppo_timesteps"), 50_000),
        max_stage_wall_sec=_coerce_int(cur_raw.get("max_stage_wall_sec"), 14_400),
        stage2_hold_stagnation_rollouts=_coerce_int(cur_raw.get("stage2_hold_stagnation_rollouts"), 8),
        stage1_winrate_stagnation_rollouts=_coerce_int(
            cur_raw.get("stage1_winrate_stagnation_rollouts"), 8
        ),
        checkpoint_interval_sec=_coerce_int(cur_raw.get("checkpoint_interval_sec"), 600),
        max_certificate_remediation_attempts=_coerce_int(
            cur_raw.get("max_certificate_remediation_attempts"), 5
        ),
        allow_provisional_pass=bool(cur_raw.get("allow_provisional_pass", False)),
        stage3_winrate_floor=max(
            0.20,
            min(0.55, _coerce_float(cur_raw.get("stage3_winrate_floor"), 0.35)),
        ),
        stage3_hold_ratio_max=max(
            0.40,
            min(0.95, _coerce_float(cur_raw.get("stage3_hold_ratio_max"), 0.70)),
        ),
        stage3_use_rolling_pass=bool(cur_raw.get("stage3_use_rolling_pass", True)),
        certified_max_rollouts_per_stage=_coerce_int(
            cur_raw.get("certified_max_rollouts_per_stage"), 200
        ),
        certified_stage_stall_wall_sec=_coerce_int(
            cur_raw.get("certified_stage_stall_wall_sec"),
            _coerce_int(cur_raw.get("max_stage_wall_sec"), 14_400),
        ),
        adaptation_enabled=bool(cur_raw.get("adaptation_enabled", True)),
        wall_behavior=_coerce_wall_behavior(cur_raw.get("wall_behavior", "adaptive")),
        max_stage_retries=_coerce_int(cur_raw.get("max_stage_retries"), 3),
        max_adaptation_tiers=_coerce_int(cur_raw.get("max_adaptation_tiers"), 4),
        auto_expand_on_adaptation=bool(cur_raw.get("auto_expand_on_adaptation", True)),
        exploration_chunk_size=_coerce_int(cur_raw.get("exploration_chunk_size"), 8),
        winrate_trend_window=_coerce_int(cur_raw.get("winrate_trend_window"), 12),
        negative_slope_threshold=_coerce_float(cur_raw.get("negative_slope_threshold"), -0.005),
        velocity_stall_attempt_threshold=max(
            5,
            min(80, _coerce_int(cur_raw.get("velocity_stall_attempt_threshold"), 32)),
        ),
        velocity_stall_epsilon=_coerce_float(cur_raw.get("velocity_stall_epsilon"), 0.002),
        velocity_stall_min_history_samples=max(
            3, min(20, _coerce_int(cur_raw.get("velocity_stall_min_history_samples"), 5))
        ),
        strong_recovery_escalation_boost=max(
            1, _coerce_int(cur_raw.get("strong_recovery_escalation_boost"), 2)
        ),
        reward_trend_window=_coerce_int(cur_raw.get("reward_trend_window"), 12),
        strong_recovery_explore_fraction=max(
            0.25,
            min(1.0, _coerce_float(cur_raw.get("strong_recovery_explore_fraction"), 0.5)),
        ),
        strong_recovery_oracle_stride_divisor=max(
            1, _coerce_int(cur_raw.get("strong_recovery_oracle_stride_divisor"), 2)
        ),
        strong_recovery_pattern_multiplier=max(
            1, _coerce_int(cur_raw.get("strong_recovery_pattern_multiplier"), 2)
        ),
        strong_recovery_expand_every_attempts=max(
            1, _coerce_int(cur_raw.get("strong_recovery_expand_every_attempts"), 3)
        ),
        strong_recovery_no_improvement_threshold=max(
            5, _coerce_int(cur_raw.get("strong_recovery_no_improvement_threshold"), 12)
        ),
        intra_stage1_enabled=bool(cur_raw.get("intra_stage1_enabled", True)),
        intra_initial_hard_pct=max(
            0.0, min(1.0, _coerce_float(cur_raw.get("intra_initial_hard_pct"), 0.15))
        ),
        intra_max_hard_pct=max(
            0.05, min(1.0, _coerce_float(cur_raw.get("intra_max_hard_pct"), 0.70))
        ),
        intra_hard_pct_step=max(0.01, _coerce_float(cur_raw.get("intra_hard_pct_step"), 0.05)),
        intra_easy_winrate_target=max(
            0.1, min(0.95, _coerce_float(cur_raw.get("intra_easy_winrate_target"), 0.50))
        ),
        intra_easy_stability_window=max(1, _coerce_int(cur_raw.get("intra_easy_stability_window"), 3)),
        intra_easy_percentile=max(
            0.05, min(0.80, _coerce_float(cur_raw.get("intra_easy_percentile"), 0.40))
        ),
        intra_hard_percentile=max(
            0.05, min(0.80, _coerce_float(cur_raw.get("intra_hard_percentile"), 0.40))
        ),
        intra_pool_size_multiplier=max(1, _coerce_int(cur_raw.get("intra_pool_size_multiplier"), 4)),
        meta_controller_enabled=bool(cur_raw.get("meta_controller_enabled", True)),
        meta_reward_tweak_step=max(
            0.01, _coerce_float(cur_raw.get("meta_reward_tweak_step"), 0.05)
        ),
        meta_max_expectancy_coeff=max(
            0.1, min(2.0, _coerce_float(cur_raw.get("meta_max_expectancy_coeff"), 0.75))
        ),
        meta_pattern_yield_floor=max(
            0.0, min(1.0, _coerce_float(cur_raw.get("meta_pattern_yield_floor"), 0.15))
        ),
        meta_improving_velocity_multiplier=max(
            1.0, _coerce_float(cur_raw.get("meta_improving_velocity_multiplier"), 1.5)
        ),
        meta_review_interval_rollouts=max(
            1, _coerce_int(cur_raw.get("meta_review_interval_rollouts"), 5)
        ),
    )


__all__ = ["curriculum_kwargs"]
