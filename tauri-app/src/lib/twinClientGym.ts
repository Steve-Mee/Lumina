/** Twin gym session API (store/HUD residual split). */
import type { TwinDecision, TwinLabelResponse, TwinMetrics } from "@/lib/twinClientTypes";
import { twinFetch } from "@/lib/twinClientCore";

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
