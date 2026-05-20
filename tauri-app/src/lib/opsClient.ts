import { resolveBackendBaseUrl } from "@/lib/setupClient";
import { resolveMonitoringApiKey, monitoringFetch } from "@/lib/monitoringClient";

export interface OpsData {
  twin_decisions: Array<Record<string, unknown>>;
  gate_rejections: Array<Record<string, unknown>>;
  shadow_runs: Record<string, unknown>;
  daily_pnl_trend: Array<Record<string, unknown>>;
}

export interface StabilityReport {
  READY_FOR_REAL?: boolean;
  status?: string;
  consecutive_green_days?: number;
  days_to_green?: number;
  failures?: string[];
  criteria?: Record<string, Record<string, unknown>>;
  [key: string]: unknown;
}

export async function fetchOpsData(): Promise<OpsData> {
  return monitoringFetch<OpsData>("/api/monitoring/ops-data");
}

export async function fetchStabilityReport(): Promise<StabilityReport> {
  return monitoringFetch<StabilityReport>("/api/monitoring/stability-report");
}

export interface TrainingReport {
  timestamp?: string;
  _run_type?: string;
  _path?: string;
  [key: string]: unknown;
}

export async function fetchTrainingReports(limit = 10): Promise<TrainingReport[]> {
  const payload = await monitoringFetch<{ reports?: TrainingReport[] }>(
    `/api/monitoring/training-reports?limit=${limit}`,
  );
  return payload.reports ?? [];
}

export async function fetchLogTail(limit = 50): Promise<{ lines: string[] }> {
  return monitoringFetch(`/api/monitoring/logs/tail?limit=${limit}`);
}

export interface LeaderboardRow {
  participant: string;
  mode: string;
  trades: number;
  wins?: number;
  losses?: number;
  total_pnl: number;
  avg_pnl?: number;
  win_rate?: number;
  is_lumina?: number;
}

export async function fetchLeaderboard(): Promise<LeaderboardRow[]> {
  const base = resolveBackendBaseUrl();
  const response = await fetch(`${base}/leaderboard`, {
    headers: { Accept: "application/json" },
    cache: "no-store",
  });
  if (!response.ok) throw new Error(`Leaderboard HTTP ${response.status}`);
  const data = (await response.json()) as { leaderboard?: LeaderboardRow[] } | LeaderboardRow[];
  if (Array.isArray(data)) return data;
  return Array.isArray(data.leaderboard) ? data.leaderboard : [];
}

export async function fetchGlobalWisdom(): Promise<Record<string, unknown>> {
  const apiKey = resolveMonitoringApiKey();
  if (!apiKey) return {};
  const base = resolveBackendBaseUrl();
  const response = await fetch(`${base}/global_wisdom`, {
    headers: { Accept: "application/json", "X-API-Key": apiKey },
    cache: "no-store",
  });
  if (!response.ok) throw new Error(`Global wisdom HTTP ${response.status}`);
  return response.json() as Promise<Record<string, unknown>>;
}

export async function deleteAllTrades(): Promise<{ deleted: number }> {
  const apiKey = resolveMonitoringApiKey();
  if (!apiKey) throw new Error("API key required");
  const base = resolveBackendBaseUrl();
  const response = await fetch(`${base}/trades`, {
    method: "DELETE",
    headers: { "X-API-Key": apiKey },
  });
  if (!response.ok) throw new Error(`Delete trades HTTP ${response.status}`);
  return response.json();
}

export async function deleteDemoData(): Promise<Record<string, number>> {
  const apiKey = resolveMonitoringApiKey();
  if (!apiKey) throw new Error("API key required");
  const base = resolveBackendBaseUrl();
  const response = await fetch(`${base}/demo-data`, {
    method: "DELETE",
    headers: { "X-API-Key": apiKey },
  });
  if (!response.ok) throw new Error(`Delete demo HTTP ${response.status}`);
  return response.json();
}

export async function fetchOnboardingHardware(): Promise<Record<string, unknown>> {
  const base = resolveBackendBaseUrl();
  const response = await fetch(`${base}/api/setup/onboarding`, { cache: "no-store" });
  if (!response.ok) throw new Error(`Onboarding HTTP ${response.status}`);
  return response.json() as Promise<Record<string, unknown>>;
}

export interface ReconciliationStatus {
  status?: string;
  connection_state?: string;
  pending_count?: number;
  pending_symbols?: string[];
  last_error?: string | null;
}

export interface MonitoringDiagnostics {
  paths: Record<string, string>;
  structured_errors: Array<Record<string, unknown>>;
  reasoning_latency: Array<Record<string, unknown>>;
  model_load_times: Array<Record<string, unknown>>;
  twin_training: Array<Record<string, unknown>>;
  gate_rejections: Array<Record<string, unknown>>;
}

export async function fetchMonitoringDiagnostics(): Promise<MonitoringDiagnostics> {
  return monitoringFetch<MonitoringDiagnostics>("/api/monitoring/diagnostics");
}

export async function fetchWorkspaceSnapshot(): Promise<Record<string, unknown>> {
  return monitoringFetch("/api/monitoring/workspace-snapshot");
}

export async function fetchReactDashboardStatus(): Promise<{
  ready: boolean;
  reason?: string;
  react_url?: string;
}> {
  return monitoringFetch("/api/monitoring/react-dashboard-status");
}

export async function fetchAdminSetupSnapshot(): Promise<Record<string, unknown>> {
  return monitoringFetch("/api/monitoring/admin-setup-snapshot");
}

export async function fetchMetricsJson(): Promise<Record<string, unknown>> {
  return monitoringFetch("/api/monitoring/metrics/json");
}

export async function fetchReconciliationStatus(): Promise<ReconciliationStatus> {
  const apiKey = resolveMonitoringApiKey();
  if (!apiKey) return { status: "unavailable" };
  const base = resolveBackendBaseUrl();
  const response = await fetch(`${base}/reconciliation-status`, {
    headers: { Accept: "application/json", "X-API-Key": apiKey },
    cache: "no-store",
  });
  if (!response.ok) throw new Error(`Reconciliation HTTP ${response.status}`);
  return response.json() as Promise<ReconciliationStatus>;
}
