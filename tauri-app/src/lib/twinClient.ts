import { resolveBackendBaseUrl } from "@/lib/setupClient";
import { resolveMonitoringApiKey } from "@/lib/monitoringClient";

async function twinFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const apiKey = resolveMonitoringApiKey();
  if (!apiKey) {
    throw new Error("Monitoring API key not configured");
  }
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
    throw new Error(detail || `Twin HTTP ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export type TwinDecision = "approve" | "reject" | "modify";

export type TwinStakes = "high" | "routine";

export interface TwinReviewItem {
  dna_hash?: string;
  score?: number;
  confidence?: number;
  recommendation?: boolean;
  explanation?: string;
  risk_flags?: string[];
  stakes?: TwinStakes;
  already_labeled?: boolean;
  [key: string]: unknown;
}

export interface TwinLabelRecord {
  vraag: string;
  steve_antwoord: string;
  timestamp: string;
  context_dna_hash: string;
  confidence_score: number;
}

export interface TwinMetrics {
  avg_prediction_error?: number | null;
  reward?: number | null;
  training_steps?: number;
  threshold?: number;
  last_avg_error?: number | null;
  twin_steve_agreement_pct?: number | null;
  samples?: number | null;
  labels_total_recent_cap?: number;
  local_only?: boolean;
  model_path?: string;
}

export interface TwinLabelResponse {
  recorded: boolean;
  decision: TwinDecision;
  label: string;
  record: TwinLabelRecord;
  rlhf?: Record<string, unknown> | null;
  audit?: Record<string, string>;
}

export async function fetchTwinReviewQueue(
  limit = 20,
  opts?: { includeLabeled?: boolean },
): Promise<TwinReviewItem[]> {
  const includeLabeled = opts?.includeLabeled === true;
  const qs = new URLSearchParams({
    limit: String(limit),
    include_labeled: includeLabeled ? "true" : "false",
  });
  const payload = await twinFetch<{ items?: TwinReviewItem[] }>(
    `/api/twin/review-queue?${qs.toString()}`,
  );
  return Array.isArray(payload.items) ? payload.items : [];
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

export async function postTwinTrain(limit = 250): Promise<Record<string, unknown>> {
  return twinFetch("/api/twin/train", {
    method: "POST",
    body: JSON.stringify({ limit }),
  });
}

export type GymProposalSource = "historical" | "synthetic";

export interface GymProposal {
  dna_hash: string;
  summary: string;
  estimated_confidence: number;
  source: GymProposalSource;
}

export interface GymSession {
  session_id: string;
  proposals: GymProposal[];
  count: number;
  historical_count?: number;
  synthetic_count?: number;
  practice_only?: boolean;
  promotes_dna?: boolean;
}

export async function startGymSession(input?: {
  count?: number;
  prefer_historical?: boolean;
}): Promise<GymSession> {
  return twinFetch<GymSession>("/api/twin/gym/session", {
    method: "POST",
    body: JSON.stringify({
      count: input?.count ?? 4,
      prefer_historical: input?.prefer_historical ?? true,
    }),
  });
}

export async function postGymAnswer(input: {
  decision: TwinDecision;
  dna_hash: string;
  summary?: string;
  estimated_confidence?: number | null;
  notes?: string;
  session_id?: string | null;
  train_now?: boolean;
}): Promise<TwinLabelResponse & { practice_only?: boolean; metrics?: TwinMetrics | null }> {
  return twinFetch("/api/twin/gym/answer", {
    method: "POST",
    body: JSON.stringify({
      decision: input.decision,
      dna_hash: input.dna_hash,
      summary: input.summary ?? "",
      estimated_confidence: input.estimated_confidence ?? null,
      notes: input.notes ?? "",
      session_id: input.session_id ?? null,
      train_now: input.train_now ?? true,
    }),
  });
}

export function twinScoreOf(item: TwinReviewItem): number | null {
  const raw = item.score ?? item.confidence;
  if (typeof raw === "number" && Number.isFinite(raw)) return raw;
  if (typeof raw === "string") {
    const n = Number(raw);
    return Number.isFinite(n) ? n : null;
  }
  return null;
}
