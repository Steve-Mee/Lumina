import type { OnboardingPayload } from "@/lib/onboardingSteps";

/**
 * Birth exit lands on Phase Hub. First Watch starts from that charter.
 * A pending Awakening surface is not a failed exam and must not open First Watch.
 * A running clock and a real incomplete or failed attempt keep their surface.
 *
 * Phase Hub replaces the Birth screen only after a real Birth exit.
 * A stale finale after Wipe Birth or Full wipe (exit explicitly false)
 * must release the hub so Genesis and Activate Birth can show.
 * While exit is still unknown, finale keeps the handoff (no blank flash).
 */
export function birthExitKeepsPhaseHub(input: {
  birthExitOk: boolean | undefined;
  birthUiPhase: string | null | undefined;
}): boolean {
  if (input.birthExitOk === true) return true;
  if (input.birthExitOk === false) return false;
  return input.birthUiPhase === "finale";
}

export function phaseHubWhenAwakeningNotStarted(
  payload: OnboardingPayload,
): OnboardingPayload {
  if (payload.birth.birth_exit_ok !== true) return payload;
  if (payload.app_surface !== "awakening") return payload;
  if (payload.app_surface_reason !== "awakening_pending") return payload;
  return {
    ...payload,
    app_surface: "hub",
    app_surface_reason: "maturation_hub",
  };
}
