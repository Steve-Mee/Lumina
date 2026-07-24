import type { MaturationPhaseId } from "@/components/birth/GenesisMaturityLadder";
import { MATURATION_STEPS } from "@/components/birth/GenesisMaturityLadder";
import type { BirthSurface } from "@/store/birthSurfaceModel";
import type { BirthUiPhase } from "@/lib/birth/birthClientTypes";
const PHASE_IDS = new Set(MATURATION_STEPS.map((s) => s.id));

export function normalizeMaturationPhase(raw: string | null | undefined): MaturationPhaseId | null {
  const token = String(raw ?? "")
    .trim()
    .toLowerCase()
    .replace(/-/g, "_");
  if (!token) return null;
  if (PHASE_IDS.has(token as MaturationPhaseId)) {
    return token as MaturationPhaseId;
  }
  // Backend may emit compound or alias tokens.
  if (token === "proving" || token === "provingground") return "proving_ground";
  if (token === "sim" || token === "playground_sim") return "playground";
  return null;
}

/**
 * Resolve which maturation step the chrome ladder should highlight.
 * Pre-deck surfaces use local journey context; deck prefers API phase.
 */
export function resolveChromeMaturationPhase(input: {
  appPhase: string;
  birthSurface?: BirthSurface | null;
  birthUiPhase?: BirthUiPhase | null;
  apiPhase?: string | null;
}): MaturationPhaseId {
  const app = String(input.appPhase ?? "").toLowerCase();
  const surface = input.birthSurface ?? null;
  const ui = input.birthUiPhase ?? null;
  const api = normalizeMaturationPhase(input.apiPhase);

  if (app === "wizard") {
    // Operator vault + risk envelope + backend reach — journey starts here.
    return "setup";
  }

  if (app === "birth") {
    if (ui === "finale") return "awakening";
    if (surface === "running" || ui === "running" || ui === "error" || ui === "stage_stalled") {
      return "birth";
    }
    if (ui === "certificate_failed") return "awakening";
    // Neural Genesis charter / recovery pin / idle
    return "genesis";
  }

  if (app === "cockpit" || app === "deck") {
    return api ?? "playground";
  }

  return api ?? "genesis";
}
