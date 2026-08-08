"""Runway / Perfect Birth / Phase2 / phoenix fields. (M5 curriculum coercion extract)."""
from __future__ import annotations

from typing import Any

from lumina_core.birth.config_coercion_helpers import (
    _coerce_float,
    _coerce_int,
)


def curriculum_kwargs(cur_raw: dict[str, Any]) -> dict[str, Any]:
    return dict(
        stage3_edgescore_enabled=bool(cur_raw.get("stage3_edgescore_enabled", True)),
        evolution_proof_min_trades=max(
            50, _coerce_int(cur_raw.get("evolution_proof_min_trades"), 500)
        ),
        evolution_proof_min_winrate_lift=max(
            0.01, _coerce_float(cur_raw.get("evolution_proof_min_winrate_lift"), 0.05)
        ),
        evolution_proof_polish_oos_winrate_min=max(
            0.20,
            min(0.60, _coerce_float(cur_raw.get("evolution_proof_polish_oos_winrate_min"), 0.45)),
        ),
        plateau_oracle_distill_top_pct=max(
            0.05,
            min(0.50, _coerce_float(cur_raw.get("plateau_oracle_distill_top_pct"), 0.25)),
        ),
        phoenix_reset_min_full_cycles=max(
            1, _coerce_int(cur_raw.get("phoenix_reset_min_full_cycles"), 3)
        ),
        phoenix_reset_max_winrate=max(
            0.05, min(0.50, _coerce_float(cur_raw.get("phoenix_reset_max_winrate"), 0.30))
        ),
        hold_trap_hold_ratio_threshold=max(
            0.40, min(0.90, _coerce_float(cur_raw.get("hold_trap_hold_ratio_threshold"), 0.55))
        ),
        hold_trap_winrate_gap=max(
            0.01, _coerce_float(cur_raw.get("hold_trap_winrate_gap"), 0.10)
        ),
        hold_trap_recovery_hold_cap=max(
            0.20, min(0.70, _coerce_float(cur_raw.get("hold_trap_recovery_hold_cap"), 0.40))
        ),
        over_trading_flat_threshold=max(
            0.10, min(0.50, _coerce_float(cur_raw.get("over_trading_flat_threshold"), 0.30))
        ),
        over_trading_round_trip_multiplier=max(
            1.0, _coerce_float(cur_raw.get("over_trading_round_trip_multiplier"), 2.0)
        ),
        over_trading_recovery_flat_target=max(
            0.20, min(0.60, _coerce_float(cur_raw.get("over_trading_recovery_flat_target"), 0.35))
        ),
        under_activity_flat_threshold=max(
            0.50, min(0.95, _coerce_float(cur_raw.get("under_activity_flat_threshold"), 0.70))
        ),
        under_activity_recovery_flat_floor=max(
            0.40, min(0.80, _coerce_float(cur_raw.get("under_activity_recovery_flat_floor"), 0.65))
        ),
        under_activity_min_range_signals=max(
            20, _coerce_int(cur_raw.get("under_activity_min_range_signals"), 50)
        ),
        under_activity_explore_multiplier=max(
            1.0, min(8.0, _coerce_float(cur_raw.get("under_activity_explore_multiplier"), 2.0))
        ),
        stage2_flat_band_swarm_defer_steps=max(
            0, min(8, _coerce_int(cur_raw.get("stage2_flat_band_swarm_defer_steps"), 2))
        ),
        stage2_participation_envelope_enabled=bool(
            cur_raw.get("stage2_participation_envelope_enabled", True)
        ),
        stage2_participation_min_signals=max(
            10, _coerce_int(cur_raw.get("stage2_participation_min_signals"), 50)
        ),
        stage2_participation_min_dwell_bars=max(
            2, min(40, _coerce_int(cur_raw.get("stage2_participation_min_dwell_bars"), 8))
        ),
        stage2_participation_band_lo=max(
            0.10, min(0.50, _coerce_float(cur_raw.get("stage2_participation_band_lo"), 0.30))
        ),
        stage2_participation_band_hi=max(
            0.50, min(0.90, _coerce_float(cur_raw.get("stage2_participation_band_hi"), 0.70))
        ),
        stage2_participation_hysteresis=max(
            0.0, min(0.08, _coerce_float(cur_raw.get("stage2_participation_hysteresis"), 0.02))
        ),
        stage2_participation_force_open_stop_pct=max(
            0.001,
            min(0.01, _coerce_float(cur_raw.get("stage2_participation_force_open_stop_pct"), 0.0075)),
        ),
        stage2_participation_force_open_target_pct=max(
            0.002,
            min(0.05, _coerce_float(cur_raw.get("stage2_participation_force_open_target_pct"), 0.015)),
        ),
        stage2_participation_force_open_qty_frac=max(
            0.05,
            min(1.0, _coerce_float(cur_raw.get("stage2_participation_force_open_qty_frac"), 0.15)),
        ),
        policy_rollback_winrate_gap=max(
            0.005, _coerce_float(cur_raw.get("policy_rollback_winrate_gap"), 0.02)
        ),
        policy_rollback_cooldown_rollouts=max(
            1, _coerce_int(cur_raw.get("policy_rollback_cooldown_rollouts"), 8)
        ),
        intra_stage2_enabled=bool(cur_raw.get("intra_stage2_enabled", True)),
        intra_stage2_initial_hard_pct=max(
            0.0, min(0.80, _coerce_float(cur_raw.get("intra_stage2_initial_hard_pct"), 0.15))
        ),
        intra_stage2_max_hard_pct=max(
            0.10, min(0.90, _coerce_float(cur_raw.get("intra_stage2_max_hard_pct"), 0.70))
        ),
        intra_stage2_hard_pct_step=max(
            0.01, min(0.20, _coerce_float(cur_raw.get("intra_stage2_hard_pct_step"), 0.05))
        ),
        intra_stage2_easy_flat_target=max(
            0.25, min(0.70, _coerce_float(cur_raw.get("intra_stage2_easy_flat_target"), 0.40))
        ),
        intra_stage2_easy_stability_window=max(
            1, _coerce_int(cur_raw.get("intra_stage2_easy_stability_window"), 3)
        ),
        intra_stage2_easy_percentile=max(
            0.05, min(0.80, _coerce_float(cur_raw.get("intra_stage2_easy_percentile"), 0.40))
        ),
        intra_stage2_hard_percentile=max(
            0.05, min(0.80, _coerce_float(cur_raw.get("intra_stage2_hard_percentile"), 0.40))
        ),
        stall_remediation_enabled=bool(cur_raw.get("stall_remediation_enabled", True)),
        stall_remediation_max_cycles=max(
            1, _coerce_int(cur_raw.get("stall_remediation_max_cycles"), 3)
        ),
        stall_remediation_max_steps=max(
            1, min(8, _coerce_int(cur_raw.get("stall_remediation_max_steps"), 5))
        ),
        certificate_runway_enabled=bool(cur_raw.get("certificate_runway_enabled", True)),
        certificate_runway_validation_pct=max(
            0.05,
            min(0.35, _coerce_float(cur_raw.get("certificate_runway_validation_pct"), 0.15)),
        ),
        stage5_profit_val_trades=max(500, _coerce_int(cur_raw.get("stage5_profit_val_trades"), 3000)),
        stage6_risk_discipline_trades=max(
            300, _coerce_int(cur_raw.get("stage6_risk_discipline_trades"), 2000)
        ),
        stage7_holdout_profile_trades=max(
            500, _coerce_int(cur_raw.get("stage7_holdout_profile_trades"), 4000)
        ),
        runway_stage5_winrate_pass=max(
            0.30, min(0.55, _coerce_float(cur_raw.get("runway_stage5_winrate_pass"), 0.40))
        ),
        runway_stage5_hold_ratio_max=max(
            0.35, min(0.75, _coerce_float(cur_raw.get("runway_stage5_hold_ratio_max"), 0.55))
        ),
        runway_stage6_winrate_min=max(
            0.35, min(0.55, _coerce_float(cur_raw.get("runway_stage6_winrate_min"), 0.42))
        ),
        runway_stage6_sharpe_min=_coerce_float(cur_raw.get("runway_stage6_sharpe_min"), 0.20),
        runway_stage6_drawdown_max_pct=max(
            4.0, min(30.0, _coerce_float(cur_raw.get("runway_stage6_drawdown_max_pct"), 12.0))
        ),
        runway_stage7_winrate_min=max(
            0.40, min(0.55, _coerce_float(cur_raw.get("runway_stage7_winrate_min"), 0.45))
        ),
        runway_s6_oos_sanity_winrate_min=max(
            0.25, min(0.45, _coerce_float(cur_raw.get("runway_s6_oos_sanity_winrate_min"), 0.35))
        ),
        runway_micro_oos_max_trades=max(
            100, _coerce_int(cur_raw.get("runway_micro_oos_max_trades"), 800)
        ),
        stall_remediation_rollouts_per_step=max(
            1, _coerce_int(cur_raw.get("stall_remediation_rollouts_per_step"), 12)
        ),
        autonomous_recovery_enabled=bool(cur_raw.get("autonomous_recovery_enabled", True)),
        # Perfect Birth KPIs (fall back to conservative defaults)
        perfect_birth_min_twin_steve_agreement_pct=_coerce_float(
            cur_raw.get("perfect_birth_min_twin_steve_agreement_pct"), 80.0
        ),
        perfect_birth_min_autonomous_recovery_rate_pct=_coerce_float(
            cur_raw.get("perfect_birth_min_autonomous_recovery_rate_pct"), 85.0
        ),
        perfect_birth_min_auto_approved_pct=_coerce_float(
            cur_raw.get("perfect_birth_min_auto_approved_pct"), 60.0
        ),
        perfect_birth_min_shadow_twin_alignment_pct=_coerce_float(
            cur_raw.get("perfect_birth_min_shadow_twin_alignment_pct"), 75.0
        ),
        perfect_birth_min_samples_labels=max(
            5, _coerce_int(cur_raw.get("perfect_birth_min_samples_labels"), 30)
        ),
        perfect_birth_min_recovery_attempts=max(
            1, _coerce_int(cur_raw.get("perfect_birth_min_recovery_attempts"), 8)
        ),
        perfect_birth_sustained_hours=max(
            1, _coerce_int(cur_raw.get("perfect_birth_sustained_hours"), 48)
        ),
        perfect_birth_auto_declare=bool(cur_raw.get("perfect_birth_auto_declare", False)),
        # Phase 2 Autonomy foundation — fail-closed defaults
        phase2_autonomy_enabled=bool(cur_raw.get("phase2_autonomy_enabled", False)),
        phase2_dynamic_wall_enabled=bool(cur_raw.get("phase2_dynamic_wall_enabled", False)),
        phase2_self_adaptive_params_enabled=bool(
            cur_raw.get("phase2_self_adaptive_params_enabled", False)
        ),
        phase2_instance_adapt_enabled=bool(cur_raw.get("phase2_instance_adapt_enabled", False)),
        # Track B: yaml cannot hollow-flag Phase 2 — flag + evidence always required.
        # Lab bypass is only phase2_allow_sim_scaffold (explicit), never by dropping these.
        phase2_require_perfect_birth_flag=True,
        phase2_allow_sim_scaffold=bool(cur_raw.get("phase2_allow_sim_scaffold", False)),
        phase2_require_twin_for_apply=bool(cur_raw.get("phase2_require_twin_for_apply", True)),
        phase2_perfect_birth_flag_path=str(
            cur_raw.get("phase2_perfect_birth_flag_path", "state/perfect_birth_complete.flag")
            or "state/perfect_birth_complete.flag"
        ),
        phase2_require_perfect_birth_evidence=True,
        phase2_recheck_perfect_birth_kpis=bool(
            cur_raw.get("phase2_recheck_perfect_birth_kpis", False)
        ),
        phase2_execution_mode=str(
            cur_raw.get("phase2_execution_mode", "observe") or "observe"
        )
        .strip()
        .lower(),
        phoenix_loop_enabled=bool(cur_raw.get("phoenix_loop_enabled", True)),
        phoenix_max_cycles=max(1, _coerce_int(cur_raw.get("phoenix_max_cycles"), 12)),
        phoenix_widen_data_after_cycles=max(
            1, _coerce_int(cur_raw.get("phoenix_widen_data_after_cycles"), 3)
        ),
        death_spiral_repeat_threshold=max(
            2, _coerce_int(cur_raw.get("death_spiral_repeat_threshold"), 4)
        ),
        death_spiral_novelty_budget=max(
            1, _coerce_int(cur_raw.get("death_spiral_novelty_budget"), 3)
        ),
    )


__all__ = ["curriculum_kwargs"]
