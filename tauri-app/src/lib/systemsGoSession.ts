import type { AppPhase } from "@/lib/onboardingPhase";

/** Survives a WebView reload. A new OS process starts a fresh session. */
const SYSTEMS_GO_DONE_KEY = "lumina.systemsGoDone";
const OPERATOR_PHASE_KEY = "lumina.operatorPhase";

const CONCRETE_PHASES: ReadonlySet<string> = new Set([
  "wizard",
  "birth",
  "hub",
  "cockpit",
  "awakening",
  "playground",
  "apprenticeship",
  "proving_ground",
]);

export function markSystemsGoDone(): void {
  try {
    sessionStorage.setItem(SYSTEMS_GO_DONE_KEY, "1");
  } catch {
    /* private mode or a non-browser test */
  }
}

export function systemsGoAlreadyDone(): boolean {
  try {
    return sessionStorage.getItem(SYSTEMS_GO_DONE_KEY) === "1";
  } catch {
    return false;
  }
}

/** Remember the surface so a reload during a busy exam does not open Command Deck. */
export function rememberOperatorPhase(phase: string): void {
  if (!CONCRETE_PHASES.has(phase)) return;
  try {
    sessionStorage.setItem(OPERATOR_PHASE_KEY, phase);
  } catch {
    /* private mode or a non-browser test */
  }
}

export function readOperatorPhase(): AppPhase | null {
  try {
    const value = sessionStorage.getItem(OPERATOR_PHASE_KEY);
    if (value && CONCRETE_PHASES.has(value)) return value as AppPhase;
  } catch {
    /* private mode or a non-browser test */
  }
  return null;
}
