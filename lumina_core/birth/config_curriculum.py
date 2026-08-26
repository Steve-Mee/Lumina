"""Birth v2 curriculum / news / reward / root config dataclasses."""
from __future__ import annotations

from dataclasses import dataclass, field

from lumina_core.birth.birth_certificate import BirthCertificateThresholds
from lumina_core.birth.foundation_history import (
    FOUNDATION_HISTORY_EXPAND_STEPS,
    FOUNDATION_HISTORY_MAX_DAYS,
)

BRO_ENGINE_VERSION = "BRO-v2"


@dataclass(slots=True)
class BirthNewsConfig:
    primary: str = "finnhub"
    enable_cache: bool = True
    cache_path: str = "state/birth_news_cache.json"


@dataclass(slots=True)
class BirthRewardConfig:
    """Expectancy-oriented PPO training reward (birth + sim only)."""

    enabled: bool = True
    expectancy_coeff: float = 0.5
    quality_win_bonus_coeff: float = 0.25
    loss_asymmetry_coeff: float = 1.25
    volatility_penalty_coeff: float = 0.15
    atr_floor: float = 0.0005
    trend_align_bonus_coeff: float = 0.10
    drawdown_penalty_coeff: float = 0.20
    sharpe_bonus_coeff: float = 0.05
    min_risk_usd: float = 25.0
    reward_clip: float = 5.0
    rolling_trade_window: int = 50
    range_flat_bonus_coeff: float = 0.003
    range_churn_penalty_coeff: float = 0.005
    # In-band Stage-2 quality boost when expectancy gap (WR−0.50 below floor).
    range_quality_boost_coeff: float = 0.15


@dataclass(slots=True)
class BirthCurriculumConfig:
    stage1_trend_trades: int = 2000
    stage2_range_trades: int = 3000
    stage3_mixed_trades: int = 5000
    stage4_viable_trades: int = 800
    stage5_probe_trades: int = 200
    foundation_stage1_min_trades: int = 150
    foundation_stage2_min_trades: int = 250
    foundation_stage3_min_trades: int = 400
    foundation_stage4_min_trades: int = 100
    foundation_stage5_min_trades: int = 50
    stage_pass_trade_pct: float = 0.10
    stage_pass_min_trades: int = 100
    stage4_polish_ppo_steps: int = 50_000
    rollout_step_budget_multiplier: int = 40
    stall_probe_steps: int = 5000
    exploration_steps: int = 2000
    rollout_chunk_trades: int = 250
    max_rollouts_per_stage: int = 500
    max_escalation_level: int = 5
    gen0_provisional_min_trades: int = 25
    oracle_scan_stride: int = 5
    oracle_patterns_per_stage: int = 5000
    oracle_max_hold_bars: int = 120
    data_expansion_steps: tuple[int, ...] = FOUNDATION_HISTORY_EXPAND_STEPS
    stagnation_rollouts_before_expand: int = 5
    curriculum_ppo_timesteps: int = 3_000
    polish_ppo_timesteps: int = 50_000
    max_stage_wall_sec: int = 14_400
    stage2_hold_stagnation_rollouts: int = 8
    stage1_winrate_stagnation_rollouts: int = 8
    checkpoint_interval_sec: int = 600
    max_certificate_remediation_attempts: int = 5
    allow_provisional_pass: bool = False
    # Stage3 mixed foundation floors (birth baseline before evolution / OOS cert).
    stage3_winrate_floor: float = 0.35
    stage3_hold_ratio_max: float = 0.70  # diagnostic / HUD only — not a Stage-3 pass gate
    stage3_use_rolling_pass: bool = True
    certified_max_rollouts_per_stage: int = 200
    certified_stage_stall_wall_sec: int = 14_400
    adaptation_enabled: bool = True
    wall_behavior: str = "adaptive"
    max_stage_retries: int = 3
    max_adaptation_tiers: int = 4
    auto_expand_on_adaptation: bool = True
    exploration_chunk_size: int = 8
    winrate_trend_window: int = 12
    negative_slope_threshold: float = -0.005
    velocity_stall_attempt_threshold: int = 32
    velocity_stall_epsilon: float = 0.002
    velocity_stall_min_history_samples: int = 5
    strong_recovery_escalation_boost: int = 2
    reward_trend_window: int = 12
    strong_recovery_explore_fraction: float = 0.5
    strong_recovery_oracle_stride_divisor: int = 2
    strong_recovery_pattern_multiplier: int = 2
    strong_recovery_expand_every_attempts: int = 3
    strong_recovery_no_improvement_threshold: int = 12
    intra_stage1_enabled: bool = True
    intra_initial_hard_pct: float = 0.15
    intra_max_hard_pct: float = 0.70
    intra_hard_pct_step: float = 0.05
    intra_easy_winrate_target: float = 0.50
    intra_easy_stability_window: int = 3
    intra_easy_percentile: float = 0.40
    intra_hard_percentile: float = 0.40
    intra_pool_size_multiplier: int = 4
    meta_controller_enabled: bool = True
    meta_reward_tweak_step: float = 0.05
    meta_max_expectancy_coeff: float = 0.75
    meta_pattern_yield_floor: float = 0.15
    meta_improving_velocity_multiplier: float = 1.5
    meta_review_interval_rollouts: int = 5
    meta_explore_decay_improving: float = 0.65
    meta_explore_decay_stall: float = 0.50
    meta_intra_ramp_on_improving: bool = True
    meta_self_eval_enabled: bool = True
    meta_self_eval_min_stall_attempts: int = 32
    meta_self_eval_min_recovery_attempts: int = 8
    meta_self_eval_rollouts_per_strategy: int = 12
    meta_self_eval_min_velocity_gain: float = 0.003
    meta_self_eval_velocity_floor: float = 0.002
    meta_self_eval_cooldown_rollouts: int = 20
    plateau_detection_enabled: bool = True
    plateau_winrate_gap: float = 0.10
    plateau_trades_beyond_gate_multiplier: int = 3
    plateau_min_stage_trades_pct: float = 0.25
    plateau_quarantine_rollouts: int = 32
    plateau_quarantine_min_trades: int = 500
    plateau_evolution_min_ppo_steps_between_steps: int = 50_000
    plateau_evolution_max_noops_per_step: int = 3
    plateau_max_wall_sec: int = 7200
    # Compressed plateau wall when already past trades-beyond-gate hard stop.
    beyond_gate_plateau_wall_sec: int = 900
    plateau_max_evolution_steps: int = 8
    plateau_evolution_rollouts_per_step: int = 12
    plateau_evolution_max_rollouts_per_step: int = 24
    plateau_evolution_meaningful_delta: float = 0.01
    # Under hard-stop: force ladder advance after this many rollouts (compressed).
    beyond_gate_evolution_rollouts_per_step: int = 4
    max_forced_recoveries_per_plateau: int = 12
    max_adaptation_stuck_escapes: int = 3
    # Raptor v10: min rollouts after an adaptation before adaptation_stuck can fire.
    adaptation_stuck_min_rollouts: int = 5
    policy_swarm_enabled: bool = True
    policy_swarm_variants: int = 3
    policy_swarm_rollouts_per_variant: int = 4
    policy_swarm_min_trades: int = 20
    oos_proxy_enabled: bool = True
    oos_proxy_interval_trades: int = 500
    oos_proxy_sample_trades: int = 50
    oos_proxy_weight: float = 0.4
    graduation_mode: str = "evolution_deferred"
    provisional_oos_floor: float = 0.35
    plateau_save_best_policy: bool = True
    plateau_best_policy_min_trades: int = 200
    stage1_winrate_pass_threshold: float = 0.45
    stage1_winrate_pass_floor: float = 0.35
    stage1_winrate_recommended: float = 0.45
    # Experimental: pass stage1 on rolling window WR (not only lifetime).
    stage1_use_rolling_pass: bool = True
    stage1_rolling_pass_window: int = 500
    # Starship Birth Phase A — EdgeScore + entropy life-support + swarm-first.
    stage1_edgescore_enabled: bool = True
    stage1_entropy_floor: float = 0.05
    stage1_hold_ratio_min: float = 0.05
    stage1_hold_ratio_max: float = 0.85
    stage1_expectancy_floor: float = -0.15
    # Stage-2 quality floor on WR−0.50 scale (−0.15 ≡ 35% WR). Not survival −0.50.
    stage2_expectancy_floor: float = -0.15
    stage2_expectancy_quality_max_steps: int = 4
    stage2_expectancy_swarm_defer_steps: int = 2
    # Stage2 cold bootstrap: oracle net-edge harvest + PPO warm before free rollout.
    stage2_cold_bootstrap_policy: bool = True
    stage2_oracle_bootstrap_steps: int = 5000
    # Min net PnL (USD after cost) for oracle winners; 0 → use geometry cost floor only.
    stage2_min_net_oracle_pnl: float = 0.50
    # Detox Stage1 prior: reinit action/value head, keep feature encoder.
    stage2_reinit_action_head: bool = True
    stage2_bootstrap_min_buffer_reward: float = 0.0
    stage2_bootstrap_max_buffer: int = 4000
    # Pilot grade: FORCE_OPEN plant trades excluded from expectancy pass.
    stage2_skill_metric_policy_only: bool = True
    stage2_skill_min_trades: int = 150
    # Stage-2 rolling pass window (shorter than Stage-1 500 — peak capture truth).
    stage2_rolling_pass_window: int = 150
    stage2_rolling_pass_min_covered: int = 80
    # Peak capture / near-miss / restore (P0–P1) — floors unchanged.
    stage2_peak_capture_enabled: bool = True
    # Chunk scale: capture first green hop (live 36% @ 50 was lost with min=80).
    stage2_peak_min_trades: int = 50
    stage2_near_miss_exp_delta: float = 0.02  # within 2pp of −0.15 on WR−0.50 scale
    stage2_peak_restore_enabled: bool = True
    stage2_peak_collapse_wr_drop: float = 0.05
    stage2_peak_restore_min_trades_since_peak: int = 50
    stage2_peak_restore_cooldown_trades: int = 80
    # PR-L: flash green min sample after first hop above floor.
    stage2_flash_green_min_trades: int = 50
    # Durable green: ≥N consecutive green chunks (or life/rolling) before arm/thrash.
    stage2_flash_durable_min_chunks: int = 2
    # Hold clamps: geometry-respecting defaults (was 35/40 — caused stop magnet).
    stage2_flash_max_hold_bars: int = 100
    stage2_peak_block_phoenix_enabled: bool = True
    stage2_peak_phoenix_min_restores: int = 1
    stage2_peak_phoenix_min_quality_rollouts: int = 4
    stage2_swarm_block_if_peak_wr_above: float = 0.28  # mid-30s peaks (was 0.33 — never armed)
    # Exit forensics: block swarm/phoenix while stop-magnet active.
    stage2_exit_forensics_block_swarm: bool = True
    stage2_exit_forensics_stop_target_max: float = 2.5
    stage2_exit_forensics_target_share_min: float = 0.30
    stage2_exit_forensics_min_decisive: int = 40
    # P2: stricter oracle inject under quality / peak protect / anti-edge.
    stage2_quality_inject_max_patterns: int = 200
    stage2_peak_inject_max_patterns: int = 120
    stage2_beat_random_inject_max_patterns: int = 80
    # Under expectancy stall + under-band: shorter max-hold (occupancy free).
    stage2_stall_max_hold_bars: int = 80
    # In-band quality: respect geometry (~120); never 35-bar flash clamp.
    stage2_quality_max_hold_bars: int = 120
    # When stop:target ratio bad under-band, clamp hold (still ≥80 quality floor).
    stage2_exit_magnet_max_hold_bars: int = 80
    stage2_exit_magnet_stop_target_ratio: float = 2.5
    # In-band FORCE_EXIT under exp gap. Default OFF (geometry time-stop, not flatten).
    stage2_force_exit_on_expectancy_gap: bool = False
    # Early-quality: freeze/restore instead of wall.force spam.
    stage2_early_quality_freeze_enabled: bool = True
    stage2_early_quality_wall_cooldown_sec: float = 300.0
    # PR-G: peak cleared floor before volume — arm graduation protect (floors unchanged).
    stage2_peak_grad_enabled: bool = True
    stage2_peak_grad_min_trades: int = 200
    # Durable collapse drop (was 0.03 — over-restored hop noise).
    stage2_peak_grad_collapse_wr_drop: float = 0.05
    # Finish hold = quality hold (geometry path); no early FORCE_EXIT theater.
    stage2_finish_max_hold_bars: int = 100
    # After restore: freeze PPO briefly (stop destroy-after-restore), then unstick.
    stage2_ppo_freeze_after_restore_enabled: bool = True
    stage2_ppo_freeze_rollouts_after_restore: int = 3
    # Hard unstick: never freeze learning longer than this many stage trades.
    stage2_ppo_freeze_trades_after_restore: int = 120
    # Skip PPO on clearly toxic large chunks (improving chunks always allowed).
    stage2_ppo_quality_gate_enabled: bool = True
    stage2_ppo_quality_min_chunk_wr: float = 0.26
    # Flash-green quality lock (42% hop): freeze PPO until lifetime ≥ 30%.
    stage2_quality_lock_enabled: bool = True
    stage2_quality_lock_chunk_wr: float = 0.36
    stage2_quality_lock_exp_floor: float = -0.14
    # Birth/SIM: Twin may accept_champion on freeze (never wipe, never REAL).
    birth_twin_freeze_resolve_enabled: bool = True
    # Birth = survival (breathe), not pro daytrader. Skill floors apply later (Playground+).
    birth_survival_pass_enabled: bool = True
    birth_survival_wr_floor: float = 0.20
    birth_survival_expectancy_floor: float = -0.50
    birth_plant_soft_block_rate_max_per_1k: float = 100.0
    # Stage-1 foundation (learning target ≠ pass floor). Grow without theater.
    stage1_foundation_pressure_enabled: bool = True
    stage1_foundation_target_wr: float = 0.30  # learning aspire; pass stays survival
    stage1_anti_thrash_wr: float = 0.25  # below this past gate → anti-thrash meta
    # Stage-1 → Stage-2 hard transfer handoff (umbilical cut).
    stage1_transfer_handoff_enabled: bool = True
    stage1_transfer_purge_buffer: bool = True
    stage1_transfer_keep_buffer_top_pct: float = 0.0  # 0 = full clear
    stage1_transfer_max_buffer_keep: int = 0
    stage1_transfer_reinit_action_head: bool = True
    starship_entropy_life_support_enabled: bool = True
    starship_swarm_first_enabled: bool = True
    starship_exploration_burst_multiplier: float = 2.5
    starship_certified_plateau_max_evolution_steps: int = 4
    starship_stall_after_swarm_only: bool = True
    starship_champion_freeze_enabled: bool = True
    starship_champion_edgescore_gap: float = 0.02
    starship_entropy_required_after_ppo_steps: int = 500
    starship_twin_continue_when_full_auto: bool = True
    stage2_edgescore_enabled: bool = True
    # Durable Stage-2 graduation (A+C): 2× rolling + lifetime ≥ floor−δ.
    stage2_pass_durable_enabled: bool = True
    stage2_pass_rolling_streak: int = 2
    stage2_pass_lifetime_delta: float = 0.05  # life ≥ 30% when floor 35%
    # Stage-2 → Stage-3 transfer detox.
    stage2_transfer_handoff_enabled: bool = True
    stage2_transfer_purge_buffer: bool = True
    stage2_transfer_keep_buffer_top_pct: float = 0.10
    stage2_transfer_max_buffer_keep: int = 500
    stage2_transfer_reinit_action_head: bool = True
    stage2_transfer_reinit_below_wr: float = 0.32
    stage3_edgescore_enabled: bool = True
    # Durable Stage-3 graduation: no rolling-only 35% at lifetime 25%.
    stage3_pass_durable_enabled: bool = True
    stage3_pass_rolling_streak: int = 2
    stage3_pass_lifetime_delta: float = 0.05  # life ≥ 30% when floor 35%
    # Stage-3 occupancy pass: mixed-flat in band (capital preservation).
    stage3_occupancy_pass_enabled: bool = True
    stage3_position_flat_min: float = 0.25
    stage3_position_flat_max: float = 0.75
    stage3_occupancy_all_ticks: bool = True
    # Settlement honesty (S2+S3): stop/target/time-stop share vs flatten theater.
    settlement_honesty_enabled: bool = True
    settlement_min_decisive_share: float = 0.70
    # Stage-3 Participation Envelope — wide PASSTHROUGH (no 0.30–0.32 sticky pin).
    stage3_participation_envelope_enabled: bool = True
    stage3_participation_min_signals: int = 50
    stage3_participation_min_dwell_bars: int = 8
    stage3_participation_band_lo: float = 0.28
    stage3_participation_band_hi: float = 0.72
    stage3_participation_hysteresis: float = 0.0
    stage3_participation_under_band_release_hysteresis: float = 0.0
    # Same IMU window as Stage 2; pass band stays 25–75%.
    stage3_occupancy_control_window_bars: int = 500
    evolution_proof_min_trades: int = 500
    evolution_proof_min_winrate_lift: float = 0.05
    evolution_proof_polish_oos_winrate_min: float = 0.45
    evolution_proof_grandfather_missing: bool = False
    plateau_oracle_distill_top_pct: float = 0.25
    phoenix_reset_min_full_cycles: int = 3
    phoenix_reset_max_winrate: float = 0.30
    hold_trap_hold_ratio_threshold: float = 0.55
    hold_trap_winrate_gap: float = 0.10
    hold_trap_recovery_hold_cap: float = 0.40
    over_trading_flat_threshold: float = 0.30
    over_trading_round_trip_multiplier: float = 2.0
    over_trading_recovery_flat_target: float = 0.35
    # Stage2 under-activity (flat too high): explore/participation before swarm.
    under_activity_flat_threshold: float = 0.70
    under_activity_recovery_flat_floor: float = 0.65
    under_activity_min_range_signals: int = 50
    under_activity_explore_multiplier: float = 2.0
    stage2_flat_band_swarm_defer_steps: int = 2
    # Stage2 Participation Envelope — hard occupancy physics (Birth SIM only).
    stage2_participation_envelope_enabled: bool = True
    stage2_participation_min_signals: int = 50
    stage2_participation_min_dwell_bars: int = 8
    stage2_participation_band_lo: float = 0.30
    stage2_participation_band_hi: float = 0.70
    # Hysteresis for FORCE_* so flat thrash at exact 30/70% does not smother quality.
    stage2_participation_hysteresis: float = 0.02
    # Empty-suppress until flat ≥ 0.32 (settle inside exam). In-position HOLD
    # only below 0.30; 0.30–0.32 in a trade is PASSTHROUGH (not a HOLD puppet).
    stage2_participation_under_band_release_hysteresis: float = 0.02
    # Rolling occupancy IMU (control). Pass-gate stays cumulative 30–70%.
    stage2_occupancy_control_window_bars: int = 500
    # Defaults match birth micro-geometry; runtime always re-calibrates from ticks.
    stage2_participation_force_open_stop_pct: float = 0.0012
    stage2_participation_force_open_target_pct: float = 0.0020
    stage2_participation_force_open_qty_frac: float = 0.15
    policy_rollback_winrate_gap: float = 0.02
    policy_rollback_cooldown_rollouts: int = 8
    intra_stage2_enabled: bool = True
    intra_stage2_initial_hard_pct: float = 0.15
    intra_stage2_max_hard_pct: float = 0.70
    intra_stage2_hard_pct_step: float = 0.05
    intra_stage2_easy_flat_target: float = 0.40
    intra_stage2_easy_stability_window: int = 3
    intra_stage2_easy_percentile: float = 0.40
    # Easy pool must clear early-quality WR before hard ramp (not flat-only).
    intra_stage2_easy_winrate_target: float = 0.38
    intra_stage2_hard_percentile: float = 0.40
    stall_remediation_enabled: bool = True
    stall_remediation_max_cycles: int = 3
    stall_remediation_max_steps: int = 5
    certificate_runway_enabled: bool = True
    certificate_runway_validation_pct: float = 0.15
    stage5_profit_val_trades: int = 3000
    stage6_risk_discipline_trades: int = 2000
    stage7_holdout_profile_trades: int = 4000
    runway_stage5_winrate_pass: float = 0.40
    runway_stage5_hold_ratio_max: float = 0.55
    runway_stage6_winrate_min: float = 0.42
    runway_stage6_sharpe_min: float = 0.20
    runway_stage6_drawdown_max_pct: float = 12.0
    runway_stage7_winrate_min: float = 0.45
    runway_s6_oos_sanity_winrate_min: float = 0.35
    runway_micro_oos_max_trades: int = 800
    stall_remediation_rollouts_per_step: int = 12
    autonomous_recovery_enabled: bool = True
    phoenix_loop_enabled: bool = True
    phoenix_max_cycles: int = 12
    phoenix_widen_data_after_cycles: int = 3
    death_spiral_repeat_threshold: int = 3
    death_spiral_novelty_budget: int = 3

    # Perfect Birth Phase success criteria (measurable KPIs for graduation to Phase 2)
    perfect_birth_min_twin_steve_agreement_pct: float = 80.0
    perfect_birth_min_autonomous_recovery_rate_pct: float = 85.0
    perfect_birth_min_auto_approved_pct: float = 60.0
    perfect_birth_min_shadow_twin_alignment_pct: float = 75.0
    perfect_birth_min_samples_labels: int = 30
    perfect_birth_min_recovery_attempts: int = 8
    perfect_birth_sustained_hours: int = 48
    # Optional auto-declare after birth complete when full KPI conjunction passes (fail-closed default).
    perfect_birth_auto_declare: bool = False

    # Phase 2 Autonomy foundation (ADR-0034) — all default OFF / fail-closed
    phase2_autonomy_enabled: bool = False
    phase2_dynamic_wall_enabled: bool = False
    phase2_self_adaptive_params_enabled: bool = False
    phase2_instance_adapt_enabled: bool = False
    phase2_require_perfect_birth_flag: bool = True
    phase2_allow_sim_scaffold: bool = False
    phase2_require_twin_for_apply: bool = True
    phase2_perfect_birth_flag_path: str = "state/perfect_birth_complete.flag"
    phase2_require_perfect_birth_evidence: bool = True
    phase2_recheck_perfect_birth_kpis: bool = False
    # observe | shadow | apply — default observe (no mutation until promoted)
    phase2_execution_mode: str = "observe"


@dataclass(slots=True)
class BirthV2Config:
    curriculum: BirthCurriculumConfig = field(default_factory=BirthCurriculumConfig)
    news: BirthNewsConfig = field(default_factory=BirthNewsConfig)
    reward: BirthRewardConfig = field(default_factory=BirthRewardConfig)
    holdout_pct: float = 0.20
    certificate_thresholds: BirthCertificateThresholds = field(default_factory=BirthCertificateThresholds)
    prefer_real_data_only: bool = True
    max_real_days: int = FOUNDATION_HISTORY_MAX_DAYS
    # C3: fraction of this load's requested days (start/expand rung), never the ceiling.
    training_window_min_ratio: float = 0.95
    # When True, short history is allowed only with degraded_data_mode + needs_attention (never silent)
    allow_degraded_data_mode: bool = False
    ppo_update_timesteps: int = 25_000
    chunk_size: int = 50_000
    trade_budget_cap: int = 10_000
