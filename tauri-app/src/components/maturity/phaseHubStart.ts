/** Follow a Phase Hub start until the runner idles, then describe the honest outcome. */
import type { MaturityHubPayload } from "@/lib/maturationClient";
import { describePhaseStartOutcome } from "@/components/maturity/phaseHubFormat";
import { setPreferApprenticeshipHub } from "@/lib/apprenticeship/apprenticeshipSurfacePref";
import { setPreferAwakeningHub } from "@/lib/awakening/awakeningSurfacePref";
import { setPreferPlaygroundHub } from "@/lib/playground/playgroundSurfacePref";
import { setPreferProvingGroundHub } from "@/lib/provingGround/provingGroundSurfacePref";

const LIVING_PHASES = new Set(["awakening", "playground", "apprenticeship", "proving_ground"]);

export function clearLivingHubPref(phase: string): void {
  if (phase === "awakening") setPreferAwakeningHub(false);
  if (phase === "playground") setPreferPlaygroundHub(false);
  if (phase === "apprenticeship") setPreferApprenticeshipHub(false);
  if (phase === "proving_ground") setPreferProvingGroundHub(false);
}

export async function maybeOpenLivingCinematic(
  phase: string,
  refresh: () => Promise<unknown>,
): Promise<boolean> {
  if (!LIVING_PHASES.has(phase)) return false;
  await refresh();
  return true;
}

export async function followPhaseStart(
  fetchHub: () => Promise<MaturityHubPayload>,
  startedPhase: string,
  opts?: { attempts?: number; delayMs?: number },
): Promise<{ ok: boolean; message: string; hub: MaturityHubPayload }> {
  const attempts = opts?.attempts ?? 20;
  const delayMs = opts?.delayMs ?? 150;
  let hub = await fetchHub();
  for (let i = 0; i < attempts && hub.runner_active; i += 1) {
    await new Promise((resolve) => {
      setTimeout(resolve, delayMs);
    });
    hub = await fetchHub();
  }
  const outcome = describePhaseStartOutcome(hub, startedPhase);
  return { ...outcome, hub };
}
