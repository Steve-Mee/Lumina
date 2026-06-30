import { resolveBackendBaseUrl } from "@/lib/setupClient";

export interface MaturationProgressPayload {
  current_phase: string;
  milestones_reached: string[];
  updated_at: string;
  real_trading_eligible: boolean;
  real_trading_blockers?: string[];
  evolution_proof_ok: boolean;
  certificate_ok: boolean;
  phases: string[];
}

export async function fetchMaturationProgress(): Promise<MaturationProgressPayload> {
  const base = resolveBackendBaseUrl();
  const response = await fetch(`${base}/api/maturity/progress`, {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    throw new Error(`Maturity progress HTTP ${response.status}`);
  }
  return response.json() as Promise<MaturationProgressPayload>;
}

export async function postApproveReal(): Promise<{ ok: boolean }> {
  const base = resolveBackendBaseUrl();
  const response = await fetch(`${base}/api/maturity/approve-real`, {
    method: "POST",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify({ confirm: true }),
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Approve REAL HTTP ${response.status}`);
  }
  return response.json() as Promise<{ ok: boolean }>;
}
