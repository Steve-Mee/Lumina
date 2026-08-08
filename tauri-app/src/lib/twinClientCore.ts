/** Twin HTTP core + review/metrics API (store/HUD residual split). */
import { luminaFetch, readHttpErrorDetail } from "@/lib/httpClient";
import { resolveMonitoringApiKey } from "@/lib/monitoringClient";
import { resolveBackendBaseUrl } from "@/lib/setupClient";
import type {
  TwinDecision,
  TwinLabelRecord,
  TwinLabelResponse,
  TwinMetrics,
  TwinModeStatus,
  TwinModeTarget,
  TwinPromoteResponse,
  TwinReviewItem,
  TwinReviewQueueResponse,
  TwinTrainResponse,
} from "@/lib/twinClientTypes";

export async function twinFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const apiKey = resolveMonitoringApiKey();
  if (!apiKey) {
    throw new Error("Monitoring API key not configured");
  }
  const base = resolveBackendBaseUrl();
  const response = await luminaFetch(`${base}${path}`, {
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
    throw new Error(await readHttpErrorDetail(response));
  }
  return response.json() as Promise<T>;
}

export function buildReviewQueueQuery(
  limit = 20,
  opts?: { includeLabeled?: boolean },
): string {
  const includeLabeled = opts?.includeLabeled === true;
  const qs = new URLSearchParams({
    limit: String(limit),
    include_labeled: includeLabeled ? "true" : "false",
  });
  return qs.toString();
}

/**
 * True when readiness value is an explicit ready signal.
 * Backend TwinModePromotionGate uses `{ promoted, fail_reasons, reason }`.
 */
export function isModeReady(value: unknown): boolean {
  if (value === true) return true;
  if (value && typeof value === "object") {
    const rec = value as Record<string, unknown>;
    if (rec.promoted === true) return true;
    if (rec.ready === true || rec.ok === true || rec.passed === true) return true;
    if (typeof rec.ready === "boolean") return rec.ready;
  }
  return false;
}

export async function fetchTwinReviewQueue(
  limit = 20,
  opts?: { includeLabeled?: boolean },
): Promise<TwinReviewItem[]> {
  const payload = await fetchTwinReviewQueueFull(limit, opts);
  return payload.items;
}

export async function fetchTwinReviewQueueFull(
  limit = 20,
  opts?: { includeLabeled?: boolean },
): Promise<TwinReviewQueueResponse> {
  const qs = buildReviewQueueQuery(limit, opts);
  const payload = await twinFetch<TwinReviewQueueResponse>(
    `/api/twin/review-queue?${qs}`,
  );
  return {
    items: Array.isArray(payload.items) ? payload.items : [],
    count: typeof payload.count === "number" ? payload.count : 0,
    high_stakes_count: payload.high_stakes_count,
    include_labeled: payload.include_labeled,
    local_only: payload.local_only,
    path: payload.path,
  };
}

export async function fetchTwinLabels(limit = 40): Promise<TwinLabelRecord[]> {
  const payload = await twinFetch<{ labels?: TwinLabelRecord[] }>(
    `/api/twin/labels?limit=${limit}`,
  );
  return Array.isArray(payload.labels) ? payload.labels : [];
}

export async function fetchTwinMetrics(): Promise<TwinMetrics> {
  return twinFetch<TwinMetrics>("/api/twin/metrics");
}

export async function fetchTwinMode(): Promise<TwinModeStatus> {
  return twinFetch<TwinModeStatus>("/api/twin/mode");
}

export async function postTwinLabel(input: {
  decision: TwinDecision;
  dna_hash: string;
  notes?: string;
  twin_score?: number | null;
  twin_recommendation?: boolean | null;
  explanation?: string;
  risk_flags?: string[];
  train_now?: boolean;
}): Promise<TwinLabelResponse> {
  return twinFetch<TwinLabelResponse>("/api/twin/label", {
    method: "POST",
    body: JSON.stringify({
      decision: input.decision,
      dna_hash: input.dna_hash,
      notes: input.notes ?? "",
      twin_score: input.twin_score ?? null,
      twin_recommendation: input.twin_recommendation ?? null,
      explanation: input.explanation ?? "",
      risk_flags: input.risk_flags ?? [],
      train_now: input.train_now ?? true,
    }),
  });
}

export async function postTwinTrain(limit = 250): Promise<TwinTrainResponse> {
  return twinFetch<TwinTrainResponse>("/api/twin/train", {
    method: "POST",
    body: JSON.stringify({ limit }),
  });
}

export async function postTwinPromote(
  target: TwinModeTarget,
): Promise<TwinPromoteResponse> {
  return twinFetch<TwinPromoteResponse>("/api/twin/promote", {
    method: "POST",
    body: JSON.stringify({ target }),
  });
}
