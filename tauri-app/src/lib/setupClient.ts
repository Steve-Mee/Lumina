import type { OnboardingPayload } from "@/lib/onboardingSteps";

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
  const response = await fetch(`${base}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `HTTP ${response.status}`);
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

export async function postConfigure(body: ConfigurePayload): Promise<{ success: boolean; steps: unknown[] }> {
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

export async function startBirth(targetTrades: number): Promise<Record<string, unknown>> {
  const base = resolveBackendBaseUrl();
  const params = new URLSearchParams({
    explicit_user_start: "true",
    target_trades: String(targetTrades),
  });
  const response = await fetch(`${base}/api/birth/start?${params}`, { method: "POST" });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `HTTP ${response.status}`);
  }
  return response.json();
}

export type {
  BirthProgressPayload,
  BirthStatusPayload,
} from "@/lib/birthClient";
export { fetchBirthStatusTyped as fetchBirthStatus } from "@/lib/birthClient";

export async function probeBackendHealth(): Promise<boolean> {
  try {
    const base = resolveBackendBaseUrl();
    const response = await fetch(`${base}/api/monitoring/health`, { signal: AbortSignal.timeout(4000) });
    return response.ok;
  } catch {
    return false;
  }
}
