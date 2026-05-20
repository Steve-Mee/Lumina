import { resolveBackendBaseUrl } from "@/lib/setupClient";
import { resolveMonitoringApiKey } from "@/lib/monitoringClient";

async function runtimeFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const apiKey = resolveMonitoringApiKey();
  if (!apiKey) throw new Error("Monitoring API key not configured");
  const base = resolveBackendBaseUrl();
  const response = await fetch(`${base}${path}`, {
    ...init,
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      "X-API-Key": apiKey,
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });
  if (!response.ok) {
    const detail = await response.text().catch(() => "");
    throw new Error(detail || `Runtime HTTP ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export interface RuntimeStatus {
  alive: boolean;
  pid: number | null;
  mode: string | null;
  message: string;
}

export async function fetchRuntimeStatus(): Promise<RuntimeStatus> {
  return runtimeFetch<RuntimeStatus>("/api/runtime/status");
}

export async function startEngine(mode = "auto"): Promise<{ ok: boolean; message: string; pid?: number }> {
  return runtimeFetch("/api/runtime/start", {
    method: "POST",
    body: JSON.stringify({ mode }),
  });
}

export async function stopEngine(): Promise<{ ok: boolean; message: string }> {
  return runtimeFetch("/api/runtime/stop", { method: "POST" });
}

export async function flattenPositions(): Promise<Record<string, unknown>> {
  return runtimeFetch("/orders/flatten", { method: "POST" });
}

export async function emergencyStop(): Promise<Record<string, unknown>> {
  return runtimeFetch("/orders/emergency-stop", { method: "POST" });
}

export async function stopAllActivities(): Promise<{ ok: boolean; message: string }> {
  return runtimeFetch("/api/runtime/stop-all", { method: "POST" });
}

export async function pauseTradingSafely(): Promise<{ ok: boolean; message: string }> {
  return runtimeFetch("/api/runtime/pause-trading", { method: "POST" });
}

export async function pauseTraining(): Promise<{ ok: boolean; message: string }> {
  return runtimeFetch("/api/runtime/training-pause", { method: "POST" });
}

export async function resumeTraining(): Promise<{ ok: boolean; message: string }> {
  return runtimeFetch("/api/runtime/training-resume", { method: "POST" });
}

export async function goLiveReal(): Promise<{ ok: boolean; message: string }> {
  return runtimeFetch("/api/runtime/go-live?confirm=true", { method: "POST" });
}

export async function runOvernightSim(durationMinutes = 240): Promise<{ ok: boolean; message: string }> {
  return runtimeFetch(`/api/runtime/overnight-sim?duration_minutes=${durationMinutes}`, {
    method: "POST",
  });
}

export async function resetFirstBoot(phrase: string): Promise<{ ok: boolean }> {
  const encoded = encodeURIComponent(phrase);
  return runtimeFetch(`/api/runtime/reset-first-boot?phrase=${encoded}`, { method: "POST" });
}

export async function stopBirth(): Promise<Record<string, unknown>> {
  const base = resolveBackendBaseUrl();
  const response = await fetch(`${base}/api/birth/stop`, { method: "POST" });
  if (!response.ok) throw new Error(`Birth stop HTTP ${response.status}`);
  return response.json();
}

export async function startBirthContinue(targetTrades: number): Promise<Record<string, unknown>> {
  const base = resolveBackendBaseUrl();
  const params = new URLSearchParams({
    explicit_user_start: "true",
    continue_training: "true",
    target_trades: String(targetTrades),
  });
  const response = await fetch(`${base}/api/birth/start?${params}`, { method: "POST" });
  if (!response.ok) throw new Error(await response.text());
  return response.json();
}
