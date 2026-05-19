import type { ApiEvolutionTreeResponse, EvolutionGraph } from "@/lib/evolutionTreeTypes";
import { fromApiResponse } from "@/lib/buildEvolutionGraph";

export function resolveEvolutionTreeUrl(): string {
  const base =
    import.meta.env.VITE_LUMINA_BACKEND_URL ?? "http://127.0.0.1:8000";
  return `${base.replace(/\/$/, "")}/api/evolution/tree?depth=10`;
}

export async function fetchEvolutionTree(): Promise<EvolutionGraph | null> {
  try {
    const response = await fetch(resolveEvolutionTreeUrl());
    if (!response.ok) {
      return null;
    }
    const raw: unknown = await response.json();
    if (typeof raw !== "object" || raw === null) {
      return null;
    }
    return fromApiResponse(raw as ApiEvolutionTreeResponse);
  } catch {
    return null;
  }
}
