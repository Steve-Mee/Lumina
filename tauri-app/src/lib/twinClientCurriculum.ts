/** Twin base curriculum, micro training, escalation API (ADR-0037). */
import { twinFetch } from "@/lib/twinClientCore";

export interface TwinMcChoice {
  id: string;
  label: string;
  value_signal: string;
}

export interface TwinMcQuestion {
  question_id: string;
  axis: string;
  scenario: string;
  choices: TwinMcChoice[];
  context_dna_hash: string;
  channel_policy?: string;
  allow_clarify?: boolean;
  max_clarify_chars?: number;
  estimated_seconds?: number;
  metrics_hint?: string;
}

export interface TwinReadiness {
  base_trained: boolean;
  birth_ready: boolean;
  curriculum_version?: string;
  question_count_total?: number;
  question_count_answered?: number;
  base_training_completion_pct?: number;
  estimated_seconds_left?: number;
  session_status?: string;
  mode?: string;
  escalation_rate?: number;
  avg_prediction_error?: number | null;
  local_only?: boolean;
}

export interface TwinBaseStatus {
  active?: boolean;
  session_id?: string;
  status?: string;
  total?: number;
  answered?: number;
  current_index?: number;
  progress_pct?: number;
  estimated_seconds_left?: number;
  question?: TwinMcQuestion | null;
  telegram_disabled?: boolean;
  birth_ready?: boolean;
  base_trained?: boolean;
  base_training_completion_pct?: number;
}

export interface TwinEscalationItem {
  escalation_id?: string;
  pending_id?: string;
  status?: string;
  question?: TwinMcQuestion;
  dna_hash?: string;
  expires_at?: string;
  context?: Record<string, unknown>;
}

export async function fetchTwinReadiness(): Promise<TwinReadiness> {
  return twinFetch<TwinReadiness>("/api/twin/readiness");
}

export async function startBaseTraining(
  forceRestart = false,
): Promise<TwinBaseStatus & { started?: boolean; message?: string }> {
  return twinFetch("/api/twin/base/start", {
    method: "POST",
    body: JSON.stringify({ force_restart: forceRestart }),
  });
}

export async function fetchBaseStatus(): Promise<TwinBaseStatus> {
  return twinFetch("/api/twin/base/status");
}

export async function fetchBaseNext(): Promise<TwinBaseStatus> {
  return twinFetch("/api/twin/base/next");
}

export async function submitBaseAnswer(input: {
  question_id: string;
  choice_id: string;
  clarify?: string;
  session_id?: string | null;
  train_now?: boolean;
}): Promise<Record<string, unknown>> {
  return twinFetch("/api/twin/base/answer", {
    method: "POST",
    body: JSON.stringify({
      question_id: input.question_id,
      choice_id: input.choice_id,
      clarify: input.clarify ?? "",
      session_id: input.session_id ?? null,
      train_now: input.train_now ?? true,
    }),
  });
}

export async function completeBaseTraining(): Promise<Record<string, unknown>> {
  return twinFetch("/api/twin/base/complete", { method: "POST", body: "{}" });
}

export async function startMicroSession(input?: {
  count?: number;
  dual_channel?: boolean;
  notify_telegram?: boolean;
}): Promise<Record<string, unknown>> {
  return twinFetch("/api/twin/micro/start", {
    method: "POST",
    body: JSON.stringify({
      count: input?.count ?? 3,
      dual_channel: input?.dual_channel ?? true,
      notify_telegram: input?.notify_telegram ?? true,
      prefer_historical: true,
    }),
  });
}

export async function submitMicroAnswer(input: {
  pending_id: string;
  choice_id: string;
  clarify?: string;
}): Promise<Record<string, unknown>> {
  return twinFetch("/api/twin/micro/answer", {
    method: "POST",
    body: JSON.stringify({
      pending_id: input.pending_id,
      choice_id: input.choice_id,
      clarify: input.clarify ?? "",
    }),
  });
}

export async function fetchPendingEscalations(): Promise<{
  items: TwinEscalationItem[];
  count: number;
}> {
  return twinFetch("/api/twin/escalations/pending");
}

export async function resolveEscalation(
  escalationId: string,
  input: { choice_id: string; clarify?: string },
): Promise<Record<string, unknown>> {
  return twinFetch(`/api/twin/escalations/${encodeURIComponent(escalationId)}/resolve`, {
    method: "POST",
    body: JSON.stringify({
      choice_id: input.choice_id,
      clarify: input.clarify ?? "",
      resolved_by: "deck",
    }),
  });
}

export interface TwinDecisionFeedItem {
  decision_id: string;
  dna_hash?: string;
  recommendation?: boolean;
  confidence?: number;
  lumina_question?: string;
  twin_answer?: string;
  why?: string;
  explanation?: string;
  risk_flags?: string[];
  mode?: string;
  call?: string;
  created_at?: string;
  feedback?: Record<string, unknown> | null;
}

export async function fetchTwinDecisionsRecent(
  limit = 15,
): Promise<{ items: TwinDecisionFeedItem[]; count: number }> {
  return twinFetch(`/api/twin/decisions/recent?limit=${limit}`);
}

export async function postTwinDecisionFeedback(
  decisionId: string,
  input: { action: "OK" | "A" | "V" | "M"; notes?: string },
): Promise<Record<string, unknown>> {
  return twinFetch(`/api/twin/decisions/${encodeURIComponent(decisionId)}/feedback`, {
    method: "POST",
    body: JSON.stringify({
      action: input.action,
      notes: input.notes ?? "",
      train_now: true,
    }),
  });
}
