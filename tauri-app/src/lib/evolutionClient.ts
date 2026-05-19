import { resolveBackendBaseUrl } from "@/lib/setupClient";
import { resolveMonitoringApiKey } from "@/lib/monitoringClient";

async function evolutionFetch<T>(path: string, init?: RequestInit): Promise<T> {
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
    throw new Error(detail || `Evolution HTTP ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export interface EvolutionProposal {
  hash: string;
  timestamp?: string;
  challengers?: Array<{ name?: string; hyperparam_suggestion?: Record<string, unknown> }>;
}

export async function fetchEvolutionProposals(): Promise<EvolutionProposal[]> {
  const rows = await evolutionFetch<EvolutionProposal[]>("/api/evolution/proposals");
  return Array.isArray(rows) ? rows : [];
}

export async function approveProposal(input: {
  hash: string;
  challenger_name: string;
}): Promise<unknown> {
  return evolutionFetch("/api/evolution/approve", {
    method: "POST",
    body: JSON.stringify({
      hash: input.hash,
      challenger_name: input.challenger_name,
      require_human_approval: true,
    }),
  });
}

export async function rejectProposal(input: {
  hash: string;
  reason: string;
}): Promise<unknown> {
  return evolutionFetch("/api/evolution/reject", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function resolveDefaultChallengerName(
  proposal: EvolutionProposal | undefined,
): string | null {
  const challengers = proposal?.challengers;
  if (!Array.isArray(challengers) || challengers.length === 0) return null;
  const first = challengers[0];
  return typeof first?.name === "string" ? first.name : null;
}
