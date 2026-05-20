import { resolveBackendBaseUrl } from "@/lib/setupClient";

export interface BirthProgressPayload {
  stage?: string;
  phase?: string;
  progress_pct?: number;
  trades_done?: number;
  target_trades?: number;
  cumulative_trades?: number;
  total_trades?: number;
  ppo_steps?: number;
  ppo_steps_cumulative?: number;
  ppo_batch_count?: number;
  message?: string;
}

export interface BirthStatusPayload {
  status: string;
  message?: string;
  error?: string;
  progress?: BirthProgressPayload;
  progress_pct?: number;
  artifacts_ok?: boolean;
  artifacts_label?: string;
  phase_label?: string;
  elapsed_seconds?: number;
  adaptive_intelligence?: Record<string, unknown>;
}

export interface StartBirthSessionOptions {
  targetTrades: number;
  practiceMode?: boolean;
  continueTraining?: boolean;
  force?: boolean;
}

async function postBirthStart(params: URLSearchParams): Promise<Record<string, unknown>> {
  const base = resolveBackendBaseUrl();
  const response = await fetch(`${base}/api/birth/start?${params}`, { method: "POST" });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `HTTP ${response.status}`);
  }
  return response.json();
}

export async function fetchBirthStatusTyped(): Promise<BirthStatusPayload> {
  const base = resolveBackendBaseUrl();
  const response = await fetch(`${base}/api/birth/status`);
  if (!response.ok) throw new Error(`Birth status HTTP ${response.status}`);
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
  return postBirthStart(params);
}

export async function startBirthSessionContinue(
  targetTrades: number,
): Promise<Record<string, unknown>> {
  return startBirthSession({ targetTrades, continueTraining: true });
}

export async function clearBirthForExtraTraining(): Promise<Record<string, unknown>> {
  const base = resolveBackendBaseUrl();
  const response = await fetch(`${base}/api/birth/extra-training`, { method: "POST" });
  if (!response.ok) throw new Error(`Extra training HTTP ${response.status}`);
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
