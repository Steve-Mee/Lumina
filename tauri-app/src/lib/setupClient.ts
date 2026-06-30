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

export interface ConfigurePayload {
  mode: string;
  credentials: {
    LUMINA_JWT_SECRET_KEY: string;
    CROSSTRADE_TOKEN: string;
    CROSSTRADE_ACCOUNT: string;
    LUMINA_ADMIN_API_KEY?: string;
    XAI_API_KEY?: string;
    TELEGRAM_BOT_TOKEN?: string;
    TELEGRAM_CHAT_ID?: string;
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
}> {
  return apiFetch("/api/setup/credentials", {
    method: "POST",
    body: JSON.stringify(credentials),
  });
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
};

export async function postBotConfig(
  body: BotConfigPayload,
): Promise<{ success: boolean; defaults: OnboardingPayload["defaults"] }> {
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

export type BirthStartStatus = "started" | "rejected" | "already_running" | "already_completed";

export interface BirthStartResponse {
  status: BirthStartStatus;
  message?: string;
  target_trades?: number;
}

export function isBirthStartSuccessful(status: BirthStartStatus): boolean {
  return status === "started" || status === "already_running";
}

export async function startBirth(targetTrades: number): Promise<BirthStartResponse> {
  const base = resolveBackendBaseUrl();
  const params = new URLSearchParams({
    explicit_user_start: "true",
    target_trades: String(targetTrades),
  });
  const response = await luminaFetch(`${base}/api/birth/start?${params}`, { method: "POST" });
  if (!response.ok) {
    throw new Error(await readHttpErrorDetail(response));
  }
  return response.json() as Promise<BirthStartResponse>;
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
