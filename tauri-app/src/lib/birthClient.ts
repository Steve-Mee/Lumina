import { resolveBackendBaseUrl } from "@/lib/setupClient";
import { luminaFetch, readHttpErrorDetail } from "@/lib/httpClient";

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
  plateau_elapsed_sec?: number;
  trades_beyond_gate?: number;
  plateau_forced_recoveries_count?: number;
  plateau_best_winrate?: number;
  needs_attention?: boolean;
  attention_reason_code?: string;
  attention_summary?: string;
  attention_recommended_actions?: string[];
  attention_notified_at?: string;
  constitution_violations_session?: number;
  constitution_violations_cumulative?: number;
  loading_chunk?: number;
  chunk_total?: number;
  bars_loaded?: number;
  chunk_phase?: string;
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
  engine_version?: string;
  fast_path_eligible?: boolean;
  data_manifest?: Record<string, unknown>;
  elapsed_seconds?: number;
  adaptive_intelligence?: Record<string, unknown>;
}

export interface StartBirthSessionOptions {
  targetTrades: number;
  practiceMode?: boolean;
  continueTraining?: boolean;
  force?: boolean;
  reuseData?: boolean;
}

function isNotFoundError(err: unknown): boolean {
  const msg = err instanceof Error ? err.message : String(err);
  return msg.includes("Not Found") || msg.includes("HTTP 404");
}

async function postBirthStart(params: URLSearchParams): Promise<Record<string, unknown>> {
  const base = resolveBackendBaseUrl();
  const response = await luminaFetch(`${base}/api/birth/start?${params}`, { method: "POST" });
  if (!response.ok) {
    throw new Error(await readHttpErrorDetail(response));
  }
  return response.json();
}

async function postBirthMutation(
  path: string,
  params: URLSearchParams,
): Promise<BirthStatusPayload> {
  const base = resolveBackendBaseUrl();
  const response = await luminaFetch(`${base}${path}?${params}`, { method: "POST" });
  if (!response.ok) {
    throw new Error(await readHttpErrorDetail(response));
  }
  return response.json() as Promise<BirthStatusPayload>;
}

export async function fetchBirthStatusTyped(): Promise<BirthStatusPayload> {
  const base = resolveBackendBaseUrl();
  const response = await luminaFetch(`${base}/api/birth/status`);
  if (!response.ok) throw new Error(await readHttpErrorDetail(response));
  return response.json() as Promise<BirthStatusPayload>;
}

export async function startBirthSession(
  targetTradesOrOptions: number | StartBirthSessionOptions,
): Promise<Record<string, unknown>> {
  const options: StartBirthSessionOptions =
    typeof targetTradesOrOptions === "number"
      ? { targetTrades: targetTradesOrOptions }
      : targetTradesOrOptions;

  const params = new URLSearchParams({
    explicit_user_start: "true",
    target_trades: String(options.targetTrades),
  });
  if (options.practiceMode) {
    params.set("practice_mode", "true");
  }
  if (options.continueTraining) {
    params.set("continue_training", "true");
  }
  if (options.force) {
    params.set("force", "true");
  }
  if (options.reuseData) {
    params.set("reuse_data", "true");
  }
  return postBirthStart(params);
}

export async function startBirthSessionContinue(
  targetTrades: number,
): Promise<Record<string, unknown>> {
  return startBirthSession({ targetTrades, continueTraining: true });
}

export type BirthStartStatus = "started" | "rejected" | "already_running" | "already_completed";

export function isBirthStartSuccessful(
  status: unknown,
  payload?: Pick<BirthStatusPayload, "start_acknowledged">,
): boolean {
  if (payload?.start_acknowledged === true) {
    return true;
  }
  const normalized = String(status ?? "").toLowerCase();
  return normalized === "started" || normalized === "already_running";
}

export async function retryBirthSession(
  targetTrades: number,
  options?: { wipe?: boolean },
): Promise<BirthStatusPayload> {
  const params = new URLSearchParams({ target_trades: String(targetTrades) });
  if (options?.wipe) {
    params.set("wipe", "true");
  }
  try {
    return await postBirthMutation("/api/birth/retry", params);
  } catch (err) {
    if (options?.wipe || !isNotFoundError(err)) {
      throw err;
    }
    const fallback = new URLSearchParams({
      explicit_user_start: "true",
      target_trades: String(targetTrades),
      continue_training: "true",
    });
    const result = await postBirthStart(fallback);
    return result as unknown as BirthStatusPayload;
  }
}

export async function resumeStalledStageSession(targetTrades: number): Promise<BirthStatusPayload> {
  const params = new URLSearchParams({ target_trades: String(targetTrades) });
  try {
    return await postBirthMutation("/api/birth/resume-stage", params);
  } catch (err) {
    if (!isNotFoundError(err)) {
      throw err;
    }
    const fallback = new URLSearchParams({
      explicit_user_start: "true",
      target_trades: String(targetTrades),
      continue_training: "true",
    });
    const result = await postBirthStart(fallback);
    return result as unknown as BirthStatusPayload;
  }
}

export async function expandAndRetryStalledStageSession(
  targetTrades: number,
): Promise<BirthStatusPayload> {
  const params = new URLSearchParams({ target_trades: String(targetTrades) });
  try {
    return await postBirthMutation("/api/birth/expand-and-retry", params);
  } catch (err) {
    if (!isNotFoundError(err)) {
      throw err;
    }
    const fallback = new URLSearchParams({
      explicit_user_start: "true",
      target_trades: String(targetTrades),
      continue_training: "true",
      reuse_data: "true",
    });
    const result = await postBirthStart(fallback);
    return result as unknown as BirthStatusPayload;
  }
}

export async function resumeBirthSession(targetTrades: number): Promise<BirthStatusPayload> {
  /** Certificate-failure fast path: retry without wipe (BRO v2 SSOT). */
  return retryBirthSession(targetTrades, { wipe: false });
}

export async function reuseDataBirthSession(targetTrades: number): Promise<BirthStatusPayload> {
  const params = new URLSearchParams({ target_trades: String(targetTrades) });
  try {
    return await postBirthMutation("/api/birth/reuse-data", params);
  } catch (err) {
    if (!isNotFoundError(err)) {
      throw err;
    }
    const fallback = new URLSearchParams({
      explicit_user_start: "true",
      target_trades: String(targetTrades),
      continue_training: "true",
      reuse_data: "true",
    });
    const result = await postBirthStart(fallback);
    return result as unknown as BirthStatusPayload;
  }
}

export async function clearBirthForExtraTraining(): Promise<Record<string, unknown>> {
  const base = resolveBackendBaseUrl();
  const response = await fetch(`${base}/api/birth/extra-training`, { method: "POST" });
  if (!response.ok) throw new Error(`Extra training HTTP ${response.status}`);
  return response.json();
}

export async function wipeAllBirthData(): Promise<Record<string, unknown>> {
  const base = resolveBackendBaseUrl();
  const response = await luminaFetch(`${base}/api/birth/wipe-all?confirm=true`, { method: "POST" });
  if (!response.ok) {
    throw new Error(await readHttpErrorDetail(response));
  }
  return response.json();
}

export interface BirthSettingsPayload {
  training_trades: number;
  prefer_real_data_only: boolean;
  max_real_days: number;
  allow_minimal_synthetic_fallback: boolean;
  require_real_simulator_data: boolean;
}

export async function saveBirthSettings(body: BirthSettingsPayload): Promise<Record<string, unknown>> {
  const base = resolveBackendBaseUrl();
  const response = await fetch(`${base}/api/birth/settings`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Birth settings HTTP ${response.status}`);
  }
  return response.json();
}

export async function adjustBirthMaxDays(): Promise<{ ok: boolean; max_real_days: number }> {
  const base = resolveBackendBaseUrl();
  const response = await fetch(`${base}/api/birth/adjust-max-days`, { method: "POST" });
  if (!response.ok) throw new Error(`Adjust max days HTTP ${response.status}`);
  return response.json() as Promise<{ ok: boolean; max_real_days: number }>;
}

export async function fetchBirthLogsTail(limit = 40): Promise<{
  stderr_path: string;
  stderr_tail: string[];
  full_log_path: string;
  full_log_tail: string[];
}> {
  const base = resolveBackendBaseUrl();
  const response = await fetch(`${base}/api/birth/logs-tail?limit=${limit}`);
  if (!response.ok) throw new Error(`Birth logs HTTP ${response.status}`);
  return response.json();
}
