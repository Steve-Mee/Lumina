import type { OnboardingPayload } from "@/lib/onboardingSteps";
import { luminaFetch, readHttpErrorDetail } from "@/lib/httpClient";
import {
  persistMonitoringApiKey,
  resolveMonitoringApiKey,
} from "@/lib/monitoringClient";

const STORAGE_KEY = "lumina.backendUrl";

export function resolveBackendBaseUrl(): string {
  const stored = localStorage.getItem(STORAGE_KEY);
  if (stored?.trim()) return stored.replace(/\/$/, "");
  return (import.meta.env.VITE_LUMINA_BACKEND_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");
}

export function setBackendBaseUrl(url: string): void {
  localStorage.setItem(STORAGE_KEY, url.replace(/\/$/, ""));
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const base = resolveBackendBaseUrl();
  const response = await luminaFetch(`${base}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });
  if (!response.ok) {
    throw new Error(await readHttpErrorDetail(response));
  }
  return response.json() as Promise<T>;
}

export async function fetchOnboardingStatus(): Promise<OnboardingPayload> {
  return apiFetch<OnboardingPayload>("/api/setup/onboarding");
}

export interface FabricConnectionCheck {
  id: string;
  title: string;
  status: "pass" | "fail" | "warn" | "skip";
  message: string;
  detail?: string | null;
  duration_ms?: number;
}

export interface FabricConnectionTestReport {
  overall: "green" | "amber" | "red";
  started_at: string;
  duration_ms: number;
  target: string;
  gateway_mode: string;
  checks: FabricConnectionCheck[];
  summary: string;
  remediation: string[];
}

export interface ConfigurePayload {
  mode: string;
  credentials: {
    LUMINA_JWT_SECRET_KEY: string;
    CROSSTRADE_TOKEN: string;
    CROSSTRADE_ACCOUNT: string;
    LUMINA_ADMIN_API_KEY?: string;
    LUMINA_FABRIC_TOKEN?: string;
    XAI_API_KEY?: string;
    TELEGRAM_BOT_TOKEN?: string;
    TELEGRAM_CHAT_ID?: string;
    /** Vault emergency CrossTrade MD fallback → broker.fallback_on_fabric_failure */
    emergency_market_data_fallback?: boolean;
  };
  risk: {
    kelly_fraction: number;
    daily_loss_cap?: number | null;
    max_total_open_risk: number;
    real_capital_safety_threshold_usd: number;
  };
  evolution: {
    approval_required: boolean;
    aggressive_evolution: boolean;
    max_mutation_depth?: "conservative" | "moderate" | "radical";
  };
  training: {
    training_trades: number;
    prefer_real_data_only: boolean;
    max_real_days: number;
    allow_minimal_synthetic_fallback?: boolean;
    require_real_simulator_data?: boolean;
    stage1_winrate_pass_threshold?: number;
  };
  selected_model_key?: string;
}

export async function postCredentials(credentials: ConfigurePayload["credentials"]): Promise<{
  success: boolean;
  missing: string[];
  onboarding?: OnboardingPayload;
}> {
  return apiFetch("/api/setup/credentials", {
    method: "POST",
    body: JSON.stringify(credentials),
  });
}

/** Seed SIM defaults + mark setup complete when Vault is ready (no Risk Envelope). */
export async function postReadyForBirth(): Promise<{
  success: boolean;
  steps: Array<{ success?: boolean; message?: string; name?: string }>;
  onboarding?: OnboardingPayload;
}> {
  return apiFetch("/api/setup/ready-for-birth", {
    method: "POST",
    body: "{}",
  });
}

export interface FabricConnectionTestReportExt extends FabricConnectionTestReport {
  certified?: boolean;
}

/** SIM-only Brain ↔ NT8 Execution Fabric diagnostics (not CrossTrade). */
export async function postFabricConnectionTest(options?: {
  include_safe_mode?: boolean;
  instrument?: string;
}): Promise<FabricConnectionTestReportExt> {
  return apiFetch("/api/setup/fabric-connection-test", {
    method: "POST",
    body: JSON.stringify({
      include_safe_mode: options?.include_safe_mode ?? true,
      // Empty → backend uses trading.instrument from config (e.g. MES SEP26).
      instrument: options?.instrument ?? "",
    }),
  });
}

export interface FabricHealStep {
  id: string;
  title: string;
  status: "pass" | "fail" | "skip" | "warn";
  message: string;
  user_message?: string;
  detail?: string | null;
}

export interface FabricHealResult {
  ok: boolean;
  overall: string;
  steps: FabricHealStep[];
  needs_user: Array<{ code: string; title: string; body: string; cta: string }>;
  report: FabricConnectionTestReportExt | null;
  certified: boolean;
}

/**
 * Fabric heal pipeline.
 * Default close_ninjatrader=false — killing NT is opt-in only (user Repair).
 * Accidental callers must not force-restart the trading terminal.
 */
export async function postFabricHeal(options?: {
  close_ninjatrader?: boolean;
  launch_ninjatrader?: boolean;
  run_diagnostic?: boolean;
  allow_simhost?: boolean;
  force_redeploy?: boolean;
  wait_host_sec?: number;
}): Promise<FabricHealResult> {
  return apiFetch("/api/setup/fabric-heal", {
    method: "POST",
    body: JSON.stringify({
      close_ninjatrader: options?.close_ninjatrader ?? false,
      launch_ninjatrader: options?.launch_ninjatrader ?? true,
      run_diagnostic: options?.run_diagnostic ?? true,
      allow_simhost: options?.allow_simhost ?? false,
      force_redeploy: options?.force_redeploy ?? true,
      wait_host_sec: options?.wait_host_sec ?? 90,
    }),
  });
}

/** Live Fabric health SSOT (level ≠ paper certificate). */
export type FabricLinkLevel = "RED" | "AMBER" | "GREEN" | "RESTARTING" | string;

export type FabricLinkProof = {
  certified?: boolean;
  overall?: string;
  age_sec?: number | null;
  target?: string | null;
  stale?: boolean;
  badge_ok?: boolean;
};

export interface FabricBootstrapResult {
  token_ready: boolean;
  token_length: number;
  fabric_json: string;
  deploy: {
    deployed: boolean;
    source: string | null;
    destination: string;
    copied: string[];
    missing: string[];
    error: string | null;
  };
  gateway_mode: string;
  fabric_link_green: boolean;
  fabric_link_reason: string;
  host_ready?: boolean;
  gate_birth_ok?: boolean;
  level?: string;
  proof?: FabricLinkProof;
  certificate: Record<string, unknown> | null;
  halt: Record<string, unknown> | null;
}

export async function postFabricBootstrap(): Promise<FabricBootstrapResult> {
  return apiFetch("/api/setup/fabric-bootstrap", { method: "POST", body: "{}" });
}

export type FabricLinkStatus = {
  /** Live GREEN only (Brain connected + host up). Never paper-only. */
  green: boolean;
  /** Host running + port (or brief RESTARTING). */
  host_ready?: boolean;
  /** Birth/seal gate: host up + recent dual-plane proof. */
  gate_birth_ok?: boolean;
  gate_reason?: string;
  level?: FabricLinkLevel;
  meaning?: string;
  reason: string;
  proof?: FabricLinkProof;
  host?: Record<string, unknown>;
  live?: Record<string, unknown>;
  health?: Record<string, unknown>;
  certificate: Record<string, unknown> | null;
  halt: Record<string, unknown> | null;
};

export async function fetchFabricLinkStatus(): Promise<FabricLinkStatus> {
  return apiFetch("/api/setup/fabric-link-status");
}

/** Re-probe when NinjaTrader binary changed (fail-closed halt on RED). */
export async function postFabricNtWatch(): Promise<Record<string, unknown>> {
  return apiFetch("/api/setup/fabric-nt-watch", { method: "POST", body: "{}" });
}

export async function postConfigure(body: ConfigurePayload): Promise<{
  success: boolean;
  steps: Array<{ success?: boolean; message?: string; step?: string }>;
  onboarding?: OnboardingPayload;
}> {
  return apiFetch("/api/setup/configure", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export type BotConfigPayload = {
  mode: string;
  risk: ConfigurePayload["risk"];
  evolution: ConfigurePayload["evolution"] & {
    max_mutation_depth: "conservative" | "moderate" | "radical";
  };
  preferences?: {
    instrument: string;
    voice_enabled: boolean;
    screen_share_enabled: boolean;
    dashboard_enabled: boolean;
    runtime_trace: boolean;
    runtime_trace_interval_sec: number;
    latency_sla_ms: number;
  };
  /** Marks post-birth SIM Risk Envelope sealed (Playground unlock). */
  seal_sim_envelope?: boolean;
};

export async function postBotConfig(
  body: BotConfigPayload,
): Promise<{
  success: boolean;
  defaults: OnboardingPayload["defaults"];
  sim_envelope_sealed?: boolean | null;
}> {
  return apiFetch("/api/config/bot", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function startSmartSetup(options?: {
  install_ollama?: boolean;
  download_recommended_model?: boolean;
  selected_model_key?: string;
  force_high_tier?: boolean;
  pull_extra_models?: boolean;
}): Promise<{ status: string; message: string }> {
  return apiFetch("/api/setup/smart-setup", {
    method: "POST",
    body: JSON.stringify(options ?? {}),
  });
}

export async function generateTauriSigningKey(force = false): Promise<{
  success: boolean;
  message: string;
  key_path?: string;
  public_key?: string;
}> {
  return apiFetch("/api/setup/tauri-signing/generate", {
    method: "POST",
    body: JSON.stringify({ force }),
  });
}

export async function fetchSmartSetupProgress(): Promise<{
  running: boolean;
  status: Record<string, unknown>;
  instructions: { summary?: string; steps?: Array<{ title: string; command?: string }> };
  intelligence: Record<string, unknown>;
}> {
  return apiFetch("/api/setup/smart-setup/progress");
}

export type {
  BirthProgressPayload,
  BirthStatusPayload,
} from "@/lib/birthClient";
export { fetchBirthStatusTyped as fetchBirthStatus } from "@/lib/birthClient";

export async function probeBackendHealth(): Promise<boolean> {
  try {
    const base = resolveBackendBaseUrl();
    const response = await luminaFetch(`${base}/api/monitoring/health`, {
      signal: AbortSignal.timeout(4000),
    });
    return response.ok;
  } catch {
    return false;
  }
}

export interface DeckApiKeyResponse {
  configured: boolean;
  api_key?: string;
}

export async function fetchDeckApiKey(): Promise<DeckApiKeyResponse> {
  return apiFetch<DeckApiKeyResponse>("/api/setup/deck-api-key");
}

export type { DeckCredentialsPrefillResponse } from "@/lib/credentialsPrefill";

export async function fetchDeckCredentialsPrefill(): Promise<
  import("@/lib/credentialsPrefill").DeckCredentialsPrefillResponse
> {
  return apiFetch("/api/setup/deck-credentials-prefill");
}

/** Sync admin key from backend .env into deck localStorage when not already set. */
export async function fetchAndHydrateDeckApiKey(): Promise<boolean> {
  if (resolveMonitoringApiKey()) {
    return true;
  }
  try {
    const response = await fetchDeckApiKey();
    const key = response.api_key?.trim();
    if (response.configured && key) {
      persistMonitoringApiKey(key);
      return true;
    }
  } catch {
    // backend offline or non-localhost
  }
  return false;
}
