import { luminaFetch, readHttpErrorDetail } from "@/lib/httpClient";
import { resolveMonitoringApiKey } from "@/lib/monitoringClient";
import { resolveBackendBaseUrl } from "@/lib/setupClient";

async function twinFetch<T>(path: string, init?: RequestInit): Promise<T> {
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

export type TwinDecision = "approve" | "reject" | "modify";

export type TwinStakes = "high" | "routine";

export type TwinModeTarget = "assisted" | "full_auto" | "advisory" | "active";

export interface TwinReviewItem {
  dna_hash?: string;
  score?: number;
  confidence?: number;
  recommendation?: boolean;
  explanation?: string;
  risk_flags?: string[];
  stakes?: TwinStakes;
  already_labeled?: boolean;
  outcome?: string;
  timestamp?: string;
  [key: string]: unknown;
}

export interface TwinReviewQueueResponse {
  items: TwinReviewItem[];
  count: number;
  high_stakes_count?: number;
  include_labeled?: boolean;
  local_only?: boolean;
  path?: string;
}

export interface TwinLabelRecord {
  vraag: string;
  steve_antwoord: string;
  timestamp: string;
  context_dna_hash: string;
  confidence_score: number;
}

export interface TwinConfidenceDistribution {
  lt_50?: number;
  b50_60?: number;
  b60_80?: number;
  gte_80?: number;
  n?: number;
}

export interface TwinOutcomeCounts {
  auto_approved?: number;
  veto?: number;
  deferred?: number;
  other?: number;
}

export interface TwinModeReadiness {
  assisted?: boolean | Record<string, unknown>;
  full_auto?: boolean | Record<string, unknown>;
  [key: string]: unknown;
}

export interface TwinRollingAgreement {
  w20?: number | null;
  w50?: number | null;
  w100?: number | null;
  w20_n?: number;
  w50_n?: number;
  w100_n?: number;
  [key: string]: number | null | undefined;
}

export interface TwinAgreementPeriod {
  period?: string;
  samples?: number;
  agreement_pct?: number;
  false_positive_pct?: number;
}

export interface TwinCalibrationBucket {
  n?: number;
  mean_conf?: number | null;
  agreement_rate?: number | null;
  twin_approve_rate?: number | null;
  gt_approve_rate?: number | null;
}

export interface TwinCalibration {
  scored_samples?: number;
  buckets?: Record<string, TwinCalibrationBucket>;
  high_conf_threshold?: number;
  high_conf_samples?: number;
  high_conf_agreement_pct?: number | null;
  mean_abs_calibration_error?: number | null;
  last_avg_error?: number | null;
}

export interface TwinPromotionCriterionProgress {
  current?: number;
  required?: number;
  max_allowed?: number;
  ratio?: number;
}

export interface TwinModeTargetProgress {
  target?: string;
  ready?: boolean;
  fail_reasons?: string[];
  reason?: string;
  samples?: TwinPromotionCriterionProgress;
  agreement?: TwinPromotionCriterionProgress;
  false_positive?: TwinPromotionCriterionProgress;
  risk_flags_caught?: TwinPromotionCriterionProgress;
  constitution_adherence_pct?: number;
}

export interface TwinModePromotionProgress {
  current_mode?: string;
  authority?: string;
  thresholds?: Record<string, unknown>;
  progress?: {
    assisted?: TwinModeTargetProgress;
    full_auto?: TwinModeTargetProgress;
  };
  recent_promotions?: Record<string, unknown>[];
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
  decisions_path?: string;
  training_path?: string;
  mode?: string;
  authority?: string;
  twin_agreement_pct?: number | null;
  false_positives?: number | null;
  false_positive_pct?: number | null;
  false_negatives?: number | null;
  risk_flags_caught?: number | null;
  risk_flags_caught_pct?: number | null;
  risk_flags_missed?: number | null;
  risk_flags_missed_pct?: number | null;
  risk_flags_catch_rate_pct?: number | null;
  constitution_adherence_pct?: number | null;
  mode_samples?: number | null;
  mode_readiness?: TwinModeReadiness | null;
  mode_metrics?: Record<string, unknown> | null;
  decisions_total?: number;
  decision_window?: number;
  confidence_distribution?: TwinConfidenceDistribution | null;
  outcome_counts?: TwinOutcomeCounts | null;
  risk_flag_top?: Record<string, number> | null;
  rolling_agreement?: TwinRollingAgreement | null;
  agreement_over_time?: TwinAgreementPeriod[] | null;
  calibration?: TwinCalibration | null;
  mode_promotion_progress?: TwinModePromotionProgress | null;
  promotion_audit_tail?: Record<string, unknown>[] | null;
}

export interface TwinModeStatus {
  mode?: string;
  authority?: string;
  readiness?: TwinModeReadiness;
  mode_promotion_progress?: TwinModePromotionProgress;
  local_only?: boolean;
  [key: string]: unknown;
}

export interface TwinLabelResponse {
  recorded: boolean;
  decision: TwinDecision;
  label: string;
  record: TwinLabelRecord;
  rlhf?: Record<string, unknown> | null;
  audit?: Record<string, string>;
  local_only?: boolean;
  metrics?: TwinMetrics | null;
}

export interface TwinTrainResponse {
  result?: Record<string, unknown>;
  metrics?: TwinMetrics | null;
  local_only?: boolean;
  [key: string]: unknown;
}

export interface TwinPromoteResponse {
  promoted?: boolean;
  reason?: string;
  mode?: string;
  result?: Record<string, unknown>;
  [key: string]: unknown;
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

export async function completeGymSession(input: {
  answers: Array<{
    decision: TwinDecision;
    dna_hash: string;
    summary?: string;
    estimated_confidence?: number | null;
    notes?: string;
  }>;
  session_id?: string | null;
  train_now?: boolean;
}): Promise<Record<string, unknown>> {
  return twinFetch("/api/twin/gym/complete", {
    method: "POST",
    body: JSON.stringify({
      answers: input.answers.map((a) => ({
        decision: a.decision,
        dna_hash: a.dna_hash,
        summary: a.summary ?? "",
        estimated_confidence: a.estimated_confidence ?? null,
        notes: a.notes ?? "",
      })),
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

/** Format agreement-style percentages (0–1 or already 0–100). */
export function formatTwinPct(v: number | null | undefined): string {
  if (v == null || Number.isNaN(Number(v))) return "—";
  const n = Number(v);
  if (n <= 1.5) return `${(n * 100).toFixed(1)}%`;
  return `${n.toFixed(1)}%`;
}

export function formatTwinNum(v: number | null | undefined, digits = 3): string {
  if (v == null || Number.isNaN(Number(v))) return "—";
  return Number(v).toFixed(digits);
}

export function formatConfidenceDistribution(
  dist: TwinConfidenceDistribution | null | undefined,
): string {
  if (!dist || !dist.n) return "No scored decisions in window";
  return `n=${dist.n} · <50 ${dist.lt_50 ?? 0} · 50–60 ${dist.b50_60 ?? 0} · 60–80 ${dist.b60_80 ?? 0} · ≥80 ${dist.gte_80 ?? 0}`;
}

export function formatRollingAgreement(
  rolling: TwinRollingAgreement | null | undefined,
): string {
  if (!rolling) return "—";
  const parts: string[] = [];
  if (rolling.w20 != null) parts.push(`w20 ${formatTwinPct(rolling.w20)}`);
  if (rolling.w50 != null) parts.push(`w50 ${formatTwinPct(rolling.w50)}`);
  if (rolling.w100 != null) parts.push(`w100 ${formatTwinPct(rolling.w100)}`);
  return parts.length ? parts.join(" · ") : "—";
}

export function formatCalibrationSummary(
  calib: TwinCalibration | null | undefined,
): string {
  if (!calib || !calib.scored_samples) return "No scored comparisons yet";
  const high =
    calib.high_conf_agreement_pct != null
      ? formatTwinPct(calib.high_conf_agreement_pct)
      : "—";
  const err =
    calib.mean_abs_calibration_error != null
      ? formatTwinNum(calib.mean_abs_calibration_error, 3)
      : "—";
  return `scored ${calib.scored_samples} · high-conf agree ${high} · |calib err| ${err}`;
}

/** Compact progress bar ratio 0–1 for mode promotion criteria. */
export function promotionRatio(value: TwinPromotionCriterionProgress | null | undefined): number {
  if (!value || typeof value.ratio !== "number" || Number.isNaN(value.ratio)) return 0;
  return Math.max(0, Math.min(1, value.ratio));
}
