import { resolveBackendBaseUrl } from "@/lib/setupClient";
import { traceBirthWipe } from "@/lib/birthWipeTrace";
import { luminaFetch, readHttpErrorDetail } from "@/lib/httpClient";
import type {
  BirthSettingsPayload,
  BirthStatusPayload,
  BirthWipeApiResponse,
  StartBirthSessionOptions,
} from "@/lib/birth/birthClientTypes";
import { normalizeBirthStatusProgress } from "@/lib/birth/birthTournamentNaming";

export type {
  BirthCertificatePayload,
  BirthProgressPayload,
  BirthSettingsPayload,
  BirthStatusPayload,
  BirthWipeApiResponse,
  BirthWipeResult,
  StartBirthSessionOptions,
  TwinObservabilityPayload,
} from "@/lib/birth/birthClientTypes";

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
  const raw = (await response.json()) as BirthStatusPayload;
  return normalizeBirthStatusProgress(raw);
}

export async function stopBirthSession(): Promise<Record<string, unknown>> {
  const base = resolveBackendBaseUrl();
  const response = await luminaFetch(`${base}/api/birth/stop`, { method: "POST" });
  if (!response.ok) {
    throw new Error(await readHttpErrorDetail(response));
  }
  return response.json();
}

export async function fetchBirthStatusTyped(options?: {
  signal?: AbortSignal;
  connectTimeout?: number;
}): Promise<BirthStatusPayload> {
  const base = resolveBackendBaseUrl();
  const response = await luminaFetch(`${base}/api/birth/status`, {
    signal: options?.signal,
    connectTimeout: options?.connectTimeout ?? 30_000,
  } as RequestInit);
  if (!response.ok) throw new Error(await readHttpErrorDetail(response));
  const raw = (await response.json()) as BirthStatusPayload;
  // T12: tournament physics names primary; legacy edgescore lift aliases promoted.
  return normalizeBirthStatusProgress(raw);
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

export interface BirthStartResponse {
  status: BirthStartStatus;
  message?: string;
  target_trades?: number;
}

export async function startBirth(targetTrades: number): Promise<BirthStartResponse> {
  const params = new URLSearchParams({
    explicit_user_start: "true",
    target_trades: String(targetTrades),
  });
  const response = await luminaFetch(`${resolveBackendBaseUrl()}/api/birth/start?${params}`, { method: "POST" });
  if (!response.ok) {
    throw new Error(await readHttpErrorDetail(response));
  }
  return response.json() as Promise<BirthStartResponse>;
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

export async function autonomousRecoverySession(
  targetTrades: number,
): Promise<BirthStatusPayload> {
  const params = new URLSearchParams({ target_trades: String(targetTrades) });
  try {
    return await postBirthMutation("/api/birth/autonomous-recovery", params);
  } catch (err) {
    if (!isNotFoundError(err)) {
      throw err;
    }
    return resumeStalledStageSession(targetTrades);
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

export async function acceptChampionSession(targetTrades: number): Promise<BirthStatusPayload> {
  const params = new URLSearchParams({ target_trades: String(targetTrades) });
  try {
    return await postBirthMutation("/api/birth/accept-champion", params);
  } catch (err) {
    if (!isNotFoundError(err)) {
      throw err;
    }
    return resumeBirthSession(targetTrades);
  }
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

export async function wipeAllBirthData(options?: {
  preserveTickCache?: boolean;
}): Promise<BirthWipeApiResponse> {
  const preserveTickCache = Boolean(options?.preserveTickCache);
  const base = resolveBackendBaseUrl();
  const url = `${base}/api/birth/wipe-all?confirm=true&preserve_tick_cache=${preserveTickCache ? "true" : "false"}`;
  traceBirthWipe("client.wipe.http_start", { url, method: "POST" });
  const startedAt = performance.now();
  try {
    const response = await luminaFetch(url, { method: "POST" });
    const elapsedMs = Math.round(performance.now() - startedAt);
    traceBirthWipe("client.wipe.http_response", {
      url,
      ok: response.ok,
      status: response.status,
      elapsedMs,
    }, response.ok ? "info" : "error");
    if (!response.ok) {
      const detail = await readHttpErrorDetail(response);
      traceBirthWipe("client.wipe.http_error_body", { detail }, "error");
      throw new Error(detail);
    }
    const body = (await response.json()) as BirthWipeApiResponse;
    traceBirthWipe("client.wipe.http_json", {
      status: body.status,
      checkpointResumable: body.checkpoint_resumable,
      removedCount: Array.isArray(body.removed_artifacts) ? body.removed_artifacts.length : undefined,
    });
    return body;
  } catch (e) {
    traceBirthWipe(
      "client.wipe.http_exception",
      { error: e instanceof Error ? e.message : String(e), elapsedMs: Math.round(performance.now() - startedAt) },
      "error",
    );
    throw e;
  }
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
