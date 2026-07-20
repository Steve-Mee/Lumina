/** Birth API payload types (extracted from birthClient facade). */


export interface BirthProgressPayload {
  stage?: string;
  phase?: string;
  progress_pct?: number;
  trades_done?: number;
  target_trades?: number;
  stage_target_trades?: number;
  cumulative_trades?: number;
  total_trades?: number;
  rollout_trades?: number;
  rollout_steps?: number;
  hold_ratio?: number;
  exploration_active?: boolean;
  patterns_mined?: number;
  oracle_wins?: number;
  data_days_loaded?: number;
  expansion_step?: number;
  learning_attempt?: number;
  birth_start_time?: number;
  elapsed_sec?: number;
  stage_trades?: number;
  stage_wins?: number;
  stage_winrate?: number;
  stage_hold_ratio?: number;
  curriculum_index?: number;
  curriculum_total?: number;
  stages_passed?: string[];
  pass_criteria_id?: string;
  pass_criteria_label?: string;
  pass_metric_label?: string;
  pass_metric_target?: number;
  pass_metric_min?: number;
  pass_metric_max?: number;
  stage_display_name?: string;
  sub_phase?: string;
  sub_phase_label?: string;
  constitution_violations?: number;
  is_advancing?: boolean;
  timestamp?: string;
  ppo_steps?: number;
  ppo_steps_cumulative?: number;
  ppo_batch_count?: number;
  message?: string;
  curriculum_stage?: string;
  prior_stage?: string;
  regime_distribution_summary?: string;
  resume_cache_tier?: string;
  certificate_ok?: boolean;
  oos_metrics?: Record<string, unknown>;
  failure_reasons?: string[];
  quality_score?: number;
  remediation_attempt?: number;
  remediation_max?: number;
  remediation_action?: string;
  stage_wall_remaining_sec?: number;
  stage_range_hold_signals?: number;
  stage_range_total_signals?: number;
  stage_range_flat_bars?: number;
  stage_range_round_trips?: number;
  stage_range_flat_ratio?: number;
  stage_blocker_metric?: string;
  stage_blocker_value?: number;
  pass_reason?: string;
  provisional_pass?: boolean;
  provisional_graduation?: boolean;
  stall_diagnostics?: string | Record<string, unknown>;
  data_manifest?: Record<string, unknown>;
  actual_real_days_loaded?: number;
  regimes_covered?: string[];
  volume_gate_status?: string;
  winrate_trend_slope?: number;
  last_adaptation?: Record<string, unknown>;
  retries_this_stage?: number;
  adaptation_tier?: number;
  max_adaptation_tiers?: number;
  max_stage_retries?: number;
  auto_recovery_active?: boolean;
  adaptation_enabled?: boolean;
  wall_behavior?: string;
  escalation_level?: number;
  user_initiated_stop?: boolean;
  retryable?: boolean;
  trade_budget_remaining?: number;
  trade_budget_cap?: number;
  terminal_stall_reason?: string;
  evolution_phase?: string;
  evolution_step?: number;
  evolution_step_label?: string;
  evolution_actions_remaining?: number;
  evolution_actions_total?: number;
  evolution_actions_completed?: number;
  evolution_phantom_steps?: number;
  plateau_elapsed_sec?: number;
  trades_beyond_gate?: number;
  plateau_forced_recoveries_count?: number;
  plateau_best_winrate?: number;
  plateau_evolution_rollouts_this_step?: number;
  plateau_evolution_rollouts_max?: number;
  stall_remediation_cycle?: number;
  stall_remediation_step?: number;
  stall_remediation_max_steps?: number;
  stall_remediation_max_cycles?: number;
  recommended_recovery_action?: string;
  autonomous_recovery_pending?: boolean;
  autonomy_message?: string;
  phoenix_count?: number;
  hold_trap_detected?: boolean;
  stage1_winrate_gate?: number;
  stage1_winrate_recommended?: number;
  stage_pass_gate_trades?: number;
  stage_budget_trades?: number;
  plateau_min_stage_trades?: number;
  plateau_quarantine_active?: boolean;
  plateau_quarantine_rollouts_remaining?: number;
  plateau_quarantine_trades_remaining?: number;
  plateau_quarantine_trades_remaining_count?: number;
  plateau_quarantine_trades_new?: number;
  rolling_winrate_500?: number;
  sim_ticks_processed_cumulative?: number;
  wall_clock_rollout_sec_avg?: number;
  wall_clock_trades_per_min?: number;
  evolution_last_action_applied?: boolean;
  evolution_last_action_detail?: string;
  needs_attention?: boolean;
  attention_reason_code?: string;
  attention_summary?: string;
  attention_recommended_actions?: string[];
  attention_notified_at?: string;
  runway_phase?: string;
  birth_exit_winrate?: number;
  constitution_violations_session?: number;
  constitution_violations_cumulative?: number;
  loading_chunk?: number;
  chunk_total?: number;
  bars_loaded?: number;
  chunk_phase?: string;
  death_spiral_repeat_count?: number;
  death_spiral_last_signature?: string;
  death_spiral_circuit_breaker?: boolean;
  death_spiral_novelty_budget?: number;
  death_spiral_history?: unknown[];
  policy_swarm_active?: boolean;
  policy_swarm_variant_index?: number;
  policy_swarm_rollouts_this_variant?: number;
  policy_swarm_variant_count?: number;
  policy_swarm_committed_variant?: string;
  policy_swarm_results?: Record<string, unknown>;
  oos_proxy_winrate?: number;
  oos_proxy_trades?: number;
}

export interface BirthCertificatePayload {
  version?: string;
  oos_winrate?: number;
  oos_sharpe?: number;
  oos_max_drawdown_pct?: number;
  real_data_pct?: number;
  constitution_violations?: number;
  regimes_covered?: string[];
}

export interface BirthStatusPayload {
  status: string;
  message?: string;
  start_acknowledged?: boolean;
  error?: string;
  live?: boolean;
  progress?: BirthProgressPayload;
  progress_pct?: number;
  artifacts_ok?: boolean;
  certificate_ok?: boolean;
  certificate_reason?: string;
  certificate?: BirthCertificatePayload | null;
  curriculum_stage?: string;
  oos_metrics?: Record<string, unknown>;
  failure_reasons?: string[];
  quality_score?: number;
  remediation_attempt?: number;
  remediation_max?: number;
  checkpoint_phase?: string;
  checkpoint_quality_score?: number;
  checkpoint_resumable?: boolean;
  checkpoint_ppo_steps?: number;
  checkpoint_cumulative_trades?: number;
  checkpoint_stage_trades?: number;
  engine_version?: string;
  fast_path_eligible?: boolean;
  evolution_proof_ok?: boolean;
  real_trading_eligible?: boolean;
  runway_phase?: string;
  birth_exit_winrate?: number;
  data_manifest?: Record<string, unknown>;
  elapsed_seconds?: number;
  adaptive_intelligence?: Record<string, unknown>;
  resume_plateau_risk?: boolean;
  resume_plateau_risk_trades?: number;
  resume_plateau_risk_required?: number;
  launcher_setup?: Record<string, unknown>;
  genesis_charter?: Record<string, unknown>;
  meta_milestones?: Array<Record<string, unknown>>;
  autonomy_metrics?: Record<string, unknown> | null;
  /** Approval Twin observability during birth (mode, agreement, risk, promotion). */
  twin_observability?: TwinObservabilityPayload | null;
}

/** Compact Twin KPIs attached to birth status for operator visibility. */
export interface TwinObservabilityPayload {
  mode?: string;
  authority?: string;
  twin_steve_agreement_pct?: number | null;
  twin_agreement_pct?: number | null;
  rolling_agreement_w20?: number | null;
  rolling_agreement_w50?: number | null;
  risk_flags_caught?: number | null;
  risk_flags_missed?: number | null;
  risk_flags_catch_rate_pct?: number | null;
  high_conf_agreement_pct?: number | null;
  mean_abs_calibration_error?: number | null;
  mode_samples?: number | null;
  mode_promotion_progress?: {
    assisted_ready?: boolean;
    full_auto_ready?: boolean;
    assisted_fail_reasons?: string[];
    full_auto_fail_reasons?: string[];
    samples?: number;
  } | null;
  local_only?: boolean;
}

export interface StartBirthSessionOptions {
  targetTrades: number;
  practiceMode?: boolean;
  continueTraining?: boolean;
  force?: boolean;
  reuseData?: boolean;
}
export interface BirthWipeResult {
  ok: boolean;
  message?: string;
  removedCount?: number;
  error?: string;
}

export interface BirthWipeApiResponse {
  status?: string;
  message?: string;
  removed_artifacts?: string[];
  preserved_artifacts?: string[];
  checkpoint_resumable?: boolean;
  setup_complete?: boolean;
  redirect_to_genesis?: boolean;
  preserve_tick_cache?: boolean;
}
export type BirthUiPhase =
  | "idle"
  | "running"
  | "finale"
  | "error"
  | "certificate_failed"
  | "stage_stalled";

export interface BirthSettingsPayload {
  training_trades: number;
  prefer_real_data_only: boolean;
  max_real_days: number;
  allow_minimal_synthetic_fallback: boolean;
  require_real_simulator_data: boolean;
  /** Stage 1 winrate pass gate (0.35â€“0.45). Default 0.45. */
  stage1_winrate_pass_threshold?: number;
}
