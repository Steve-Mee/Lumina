import { resolveBackendBaseUrl } from "@/lib/setupClient";
import {
  normalizeAdaptiveIntelligenceStatus,
  normalizeTransitionSummary,
  type AdaptiveIntelligenceEventRecord,
  type AdaptiveIntelligenceStatus,
  type AdaptiveTransitionSummary,
} from "@/lib/adaptiveIntelligenceTypes";
import { normalizeLuminaMetricsPayload, type LuminaMetrics } from "@/lib/luminaMetricsModel";

export const DEFAULT_LUMINA_API_KEY_LS_KEY = "lumina_api_key";

export function resolveMonitoringApiKey(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return localStorage.getItem(DEFAULT_LUMINA_API_KEY_LS_KEY)?.trim() || null;
  } catch {
    return null;
  }
}

export function persistMonitoringApiKey(apiKey: string): void {
  if (typeof window === "undefined" || !apiKey.trim()) return;
  try {
    localStorage.setItem(DEFAULT_LUMINA_API_KEY_LS_KEY, apiKey.trim());
    void import("@/store/apiKeyStore").then(({ useApiKeyStore }) => {
      useApiKeyStore.getState().syncFromStorage();
    });
  } catch {
    // ignore storage failures
  }
}

export async function monitoringFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const base = resolveBackendBaseUrl();
  const apiKey = resolveMonitoringApiKey();
  const headers: HeadersInit = {
    Accept: "application/json",
    ...(init?.headers ?? {}),
  };
  if (apiKey) {
    (headers as Record<string, string>)["X-API-Key"] = apiKey;
  }
  const response = await fetch(`${base}${path}`, { ...init, headers, cache: "no-store" });
  if (!response.ok) {
    const detail = await response.text().catch(() => "");
    throw new Error(detail || `HTTP ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export interface AdaptiveIntelligenceLatestResponse {
  payload?: unknown;
  transition_summary?: unknown;
  timestamp?: string;
}

export async function fetchAdaptiveIntelligenceLatest(): Promise<{
  status: AdaptiveIntelligenceStatus | null;
  transitionSummary: AdaptiveTransitionSummary | null;
}> {
  const json = await monitoringFetch<AdaptiveIntelligenceLatestResponse>(
    "/api/monitoring/adaptive-intelligence/latest",
  );
  if (!json || typeof json !== "object" || Object.keys(json).length === 0) {
    return { status: null, transitionSummary: null };
  }
  return {
    status: normalizeAdaptiveIntelligenceStatus(json),
    transitionSummary: normalizeTransitionSummary(json.transition_summary),
  };
}

export async function fetchAdaptiveIntelligenceHistory(
  limit = 200,
): Promise<AdaptiveIntelligenceEventRecord[]> {
  const rows = await monitoringFetch<AdaptiveIntelligenceEventRecord[]>(
    `/api/monitoring/adaptive-intelligence/history?limit=${limit}`,
  );
  return Array.isArray(rows) ? rows : [];
}

export interface MonitoringHealthSnapshot {
  status?: string;
  uptime_s?: number;
  kill_switch_active?: boolean;
  websocket_connected?: boolean;
  current_regime?: string;
  regime_risk_state?: string;
  issues?: string[];
}

export async function fetchMonitoringHealth(): Promise<MonitoringHealthSnapshot> {
  return monitoringFetch<MonitoringHealthSnapshot>("/api/monitoring/health");
}

export async function fetchLuminaMetrics(): Promise<LuminaMetrics> {
  const json = await monitoringFetch<unknown>("/api/monitoring/metrics/json");
  return normalizeLuminaMetricsPayload(json);
}
