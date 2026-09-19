import { preferAwakeningHub } from "@/lib/awakening/awakeningSurfacePref";
import { preferApprenticeshipHub } from "@/lib/apprenticeship/apprenticeshipSurfacePref";
import { preferPlaygroundHub } from "@/lib/playground/playgroundSurfacePref";
import { preferProvingGroundHub } from "@/lib/provingGround/provingGroundSurfacePref";
import type { AppSurface, OnboardingPayload } from "@/lib/onboardingSteps";

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

  if (context.priorPhase === "birth" && context.birthPhaseCommitted) {
    return "birth";
  }

  if (payload.app_surface) {
    const mapped = surfaceToPhase(payload.app_surface);
    // Session: operator entered deck from hub — stay until they return
    if (
      mapped === "hub" &&
      context.operatorDeckActive &&
      (context.priorPhase === "cockpit" || context.operatorDeckActive)
    ) {
      return "cockpit";
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
  if (priorPhase === "cockpit" || lastPayload?.app_surface === "deck") {
    return "cockpit";
  }
  if (priorPhase === "hub" || lastPayload?.app_surface === "hub") {
    return "hub";
  }
  if (priorPhase === "birth" || lastPayload?.app_surface === "birth") {
    return "birth";
  }
  if (priorPhase === "awakening" || lastPayload?.app_surface === "awakening") {
    return "awakening";
  }
  if (priorPhase === "playground" || lastPayload?.app_surface === "playground") {
    return "playground";
  }
  if (priorPhase === "apprenticeship" || lastPayload?.app_surface === "apprenticeship") {
    return "apprenticeship";
  }
  if (priorPhase === "proving_ground" || lastPayload?.app_surface === "proving_ground") {
    return "proving_ground";
  }
  return "wizard";
}
