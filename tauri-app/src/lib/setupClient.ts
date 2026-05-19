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

export async function postConfigure(body: ConfigurePayload): Promise<{ success: boolean; steps: unknown[] }> {
  return apiFetch("/api/setup/configure", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function startSmartSetup(options?: {
  install_ollama?: boolean;
  download_recommended_model?: boolean;
}): Promise<{ status: string; message: string }> {
  return apiFetch("/api/setup/smart-setup", {
    method: "POST",
    body: JSON.stringify(options ?? {}),
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

export async function fetchBirthStatus(): Promise<Record<string, unknown>> {
  const base = resolveBackendBaseUrl();
  const response = await fetch(`${base}/api/birth/status`);
  if (!response.ok) throw new Error(`Birth status HTTP ${response.status}`);
  return response.json();
}

export async function probeBackendHealth(): Promise<boolean> {
  try {
    const base = resolveBackendBaseUrl();
    const response = await fetch(`${base}/api/monitoring/health`, { signal: AbortSignal.timeout(4000) });
    return response.ok;
  } catch {
    return false;
  }
}
