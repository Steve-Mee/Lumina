import { resolveBackendBaseUrl } from "@/lib/setupClient";

export type AdvanceMode = "manual" | "telegram" | "auto_evolve";

export interface MaturationProgressPayload {
  current_phase: string;
  milestones_reached: string[];
  updated_at: string;
  real_trading_eligible: boolean;
  real_trading_blockers?: string[];
  evolution_proof_ok: boolean;
  certificate_ok: boolean;
  phases: string[];
  advance_mode?: AdvanceMode;
  completed_phases?: string[];
  next_phase?: string | null;
  active_phase?: string | null;
  runner_active?: boolean;
}

export interface PhaseSpecDto {
  id: string;
  label: string;
  human_goal: string;
  next_id: string | null;
  entry_requires: string[];
}

export interface MaturityHubPayload {
  advance_mode: AdvanceMode;
  active_phase: string | null;
  completed_phases: string[];
  next_phase: string | null;
  focus_phase: string;
  phase_records: Record<string, {
    status?: string;
    learned?: Record<string, unknown>;
    exit_proofs?: string[];
    error?: string;
  }>;
  pending_advance: {
    from?: string;
    to?: string;
    telegram_token?: string;
    created_at?: string;
    expires_at?: string;
    ttl_sec?: number;
    remaining_sec?: number | null;
    expired?: boolean;
    status?: "active" | "expired" | string;
    has_token?: boolean;
  } | null;
  telegram_advance?: {
    mode_is_telegram?: boolean;
    pending?: MaturityHubPayload["pending_advance"];
    configured_ttl_sec?: number;
    reissue_available?: boolean;
  };
  /** M6 honesty board (Birth exit ≠ READY ≠ REAL) */
  honesty?: {
    schema?: string;
    honesty_ok?: boolean;
    next_honest_steps?: string[];
    conflation_warnings?: string[];
    ready_for_real?: { ready?: boolean };
    birth_exit?: { exited?: boolean };
    real_eligible?: { eligible?: boolean; blockers?: string[] };
  };
  next_honest_steps?: string[];
  conflation_warnings?: string[];
  birth_exit_exited?: boolean;
  ready_for_real?: boolean;
  real_eligible?: boolean;
  last_completed: string;
  learned: Record<string, unknown>;
  focus_learned: Record<string, unknown>;
  focus_status: string;
  progress_pct?: number | null;
  progress_message?: string | null;
  exit_eval: { ok: boolean; missing: string[] };
  phase_specs: Record<string, PhaseSpecDto>;
  can_start_next: boolean;
  real_requires_human: boolean;
  strict_mode?: boolean;
  experimental_soft_complete?: boolean;
  soft_legacy_complete?: boolean;
  telegram_token_ttl_sec?: number;
  runner_active?: boolean;
  last_result?: Record<string, unknown> | null;
  error?: string | null;
  updated_at?: string;
}

async function maturityJson<T>(path: string, init?: RequestInit): Promise<T> {
  const base = resolveBackendBaseUrl();
  const response = await fetch(`${base}${path}`, {
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    ...init,
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Maturity HTTP ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export async function fetchMaturationProgress(): Promise<MaturationProgressPayload> {
  return maturityJson<MaturationProgressPayload>("/api/maturity/progress");
}

export async function fetchMaturityHub(): Promise<MaturityHubPayload> {
  return maturityJson<MaturityHubPayload>("/api/maturity/hub");
}

export async function postMaturityPreferences(advanceMode: AdvanceMode): Promise<{ ok: boolean; advance_mode?: string }> {
  return maturityJson("/api/maturity/preferences", {
    method: "POST",
    body: JSON.stringify({ advance_mode: advanceMode }),
  });
}

export async function postStartMaturityPhase(phase: string): Promise<{ ok: boolean; status?: string; phase?: string }> {
  return maturityJson("/api/maturity/start-phase", {
    method: "POST",
    body: JSON.stringify({ phase, explicit_user_start: true }),
  });
}

export async function postAdvanceNextPhase(opts?: {
  confirm?: boolean;
  telegramToken?: string;
}): Promise<{ ok: boolean; status?: string; phase?: string }> {
  return maturityJson("/api/maturity/advance", {
    method: "POST",
    body: JSON.stringify({
      confirm: opts?.confirm ?? true,
      telegram_token: opts?.telegramToken ?? null,
    }),
  });
}

export async function postWipeMaturityPhase(phase: string): Promise<{ ok: boolean }> {
  return maturityJson("/api/maturity/wipe-phase", {
    method: "POST",
    body: JSON.stringify({ phase, confirm: true }),
  });
}

export async function postWipeAllMaturation(): Promise<{ ok: boolean }> {
  return maturityJson("/api/maturity/wipe-all", {
    method: "POST",
    body: JSON.stringify({ confirm: true }),
  });
}

export async function postApproveReal(): Promise<{ ok: boolean }> {
  return maturityJson("/api/maturity/approve-real", {
    method: "POST",
    body: JSON.stringify({ confirm: true }),
  });
}

export async function postRefreshTelegramAdvance(): Promise<{
  ok: boolean;
  to?: string;
  from?: string;
  expires_at?: string;
  ttl_sec?: number;
  remaining_sec?: number | null;
  has_token?: boolean;
  status?: string;
  message?: string;
}> {
  return maturityJson("/api/maturity/refresh-advance", { method: "POST", body: "{}" });
}
