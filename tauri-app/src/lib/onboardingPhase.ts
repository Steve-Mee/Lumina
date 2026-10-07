import { preferAwakeningHub } from "@/lib/awakening/awakeningSurfacePref";
import { preferApprenticeshipHub } from "@/lib/apprenticeship/apprenticeshipSurfacePref";
import { preferPlaygroundHub } from "@/lib/playground/playgroundSurfacePref";
import { preferProvingGroundHub } from "@/lib/provingGround/provingGroundSurfacePref";
import type { AppSurface, OnboardingPayload, OnboardingStepId } from "@/lib/onboardingSteps";

export type AppPhase = "loading" | "wizard" | "birth" | "hub" | "cockpit" | "awakening" | "playground" | "apprenticeship" | "proving_ground";

export interface MapAppPhaseContext {
  priorPhase: AppPhase;
  birthPhaseCommitted: boolean;
  activating: boolean;
  /** Operator reopened first-boot setup from Birth (credentials / fabric test). */
  setupReviewActive?: boolean;
  /** Operator opened Command Deck from Phase Hub (session override). */
  operatorDeckActive?: boolean;
}

const DECK_ELIGIBLE_PHASES: ReadonlySet<AppPhase> = new Set([
  "hub",
  "playground",
  "awakening",
  "apprenticeship",
  "proving_ground",
]);

function isDeckEligibleSurface(phase: AppPhase): boolean {
  return DECK_ELIGIBLE_PHASES.has(phase);
}

function surfaceToPhase(surface: AppSurface): AppPhase {
  switch (surface) {
    case "setup":
      return "wizard";
    case "birth":
      return "birth";
    case "hub":
      return "hub";
    case "deck":
      return "cockpit";
    case "awakening":
      return "awakening";
    case "playground":
      return "playground";
    case "apprenticeship":
      return "apprenticeship";
    case "proving_ground":
      return "proving_ground";
  }
}

function birthReady(payload: OnboardingPayload): boolean {
  if (payload.birth.birth_exit_ok === true) {
    return true;
  }
  if (payload.birth.birth_exit_ok === false) {
    return false;
  }
  return false;
}

/** Legacy fallback when backend omits app_surface (backward compat, max one release). */
function legacySurfaceFallback(payload: OnboardingPayload): AppPhase {
  if (!payload.backend.reachable) {
    return "wizard";
  }
  if (!payload.setup_complete) {
    return "wizard";
  }
  if (!birthReady(payload)) {
    return "birth";
  }
  return "hub";
}

/**
 * Maps backend `app_surface` SSOT to client phase with minimal in-session overrides.
 * @see docs/requests/tauri-startup-gate-implementation-plan.md
 */
export function mapAppPhase(
  payload: OnboardingPayload,
  context: MapAppPhaseContext,
): AppPhase {
  if (context.setupReviewActive) {
    return "wizard";
  }

  if (context.activating) {
    return context.priorPhase === "loading" ? "wizard" : context.priorPhase;
  }

  // Live Birth stays on the Birth screen. Once Birth has exited, the pin must
  // release — otherwise the old finale window keeps painting itself as Awakening.
  if (
    context.priorPhase === "birth" &&
    context.birthPhaseCommitted &&
    payload.birth.birth_exit_ok !== true
  ) {
    return "birth";
  }

  if (payload.app_surface) {
    const mapped = surfaceToPhase(payload.app_surface);
    // Session: operator entered deck from hub — stay until they return
    if (context.operatorDeckActive && isDeckEligibleSurface(mapped)) {
      return "cockpit";
    }
    // A live clock is the living screen. Prefer-hub is only for an idle charter.
    if (payload.app_surface_reason === `${mapped}_running`) {
      return mapped;
    }
    // Birth exit with Awakening not started is Phase Hub. Pending is not a fail.
    if (
      mapped === "awakening" &&
      payload.app_surface_reason === "awakening_pending" &&
      payload.birth.birth_exit_ok === true
    ) {
      return "hub";
    }
    if (mapped === "awakening" && preferAwakeningHub()) {
      return "hub";
    }
    if (mapped === "playground" && preferPlaygroundHub()) {
      return "hub";
    }
    if (mapped === "apprenticeship" && preferApprenticeshipHub()) {
      return "hub";
    }
    if (mapped === "proving_ground" && preferProvingGroundHub()) {
      return "hub";
    }
    return mapped;
  }

  return legacySurfaceFallback(payload);
}

/** @deprecated Use mapAppPhase — kept for transitional test imports. */
export function resolveAppPhase(
  payload: OnboardingPayload,
  priorPhase: AppPhase,
  birthPhaseCommitted: boolean,
): AppPhase {
  return mapAppPhase(payload, {
    priorPhase,
    birthPhaseCommitted,
    activating: false,
  });
}

export function shouldEnterCockpit(payload: OnboardingPayload): boolean {
  if (payload.app_surface) {
    return payload.app_surface === "deck";
  }
  return false;
}

export function shouldEnterHub(payload: OnboardingPayload): boolean {
  if (payload.app_surface) {
    return payload.app_surface === "hub";
  }
  return legacySurfaceFallback(payload) === "hub";
}

/** Marks cached payload backend unreachable after refresh failure (T8). */
export function markPayloadBackendUnreachable(
  payload: OnboardingPayload,
  error: string,
): OnboardingPayload {
  return {
    ...payload,
    backend: {
      ...payload.backend,
      reachable: false,
      error,
    },
  };
}

/**
 * Preserve operator surface when onboarding refresh fails mid-session.
 */
export function resolvePhaseOnRefreshError(
  priorPhase: AppPhase,
  lastPayload: OnboardingPayload | null,
  setupReviewActive = false,
): AppPhase {
  if (setupReviewActive) {
    return "wizard";
  }
  if (priorPhase === "loading") {
    // Cold start: stay on readiness cover until SSOT arrives (no half-wizard flash).
    if (!lastPayload) {
      return "loading";
    }
    return "wizard";
  }
  // The screen the operator is on wins. A stale hub payload must not demote a
  // living phase when the onboarding fetch fails (eval holds the API).
  if (
    priorPhase === "cockpit" ||
    priorPhase === "hub" ||
    priorPhase === "birth" ||
    priorPhase === "awakening" ||
    priorPhase === "playground" ||
    priorPhase === "apprenticeship" ||
    priorPhase === "proving_ground" ||
    priorPhase === "wizard"
  ) {
    return priorPhase;
  }
  return "wizard";
}

export const SETUP_REVIEW_STEPS: OnboardingStepId[] = ["credentials", "configuration"];

export function selectActiveSteps(
  payload: OnboardingPayload | null,
  setupReviewActive = false,
): OnboardingStepId[] {
  if (setupReviewActive) return SETUP_REVIEW_STEPS;
  if (!payload) return ["backend"];
  if (payload.wizard_steps.length > 0) return payload.wizard_steps;
  return payload.required_steps;
}
