import type { AppSurface, OnboardingPayload } from "@/lib/onboardingSteps";

export type AppPhase = "loading" | "wizard" | "birth" | "cockpit";

export interface MapAppPhaseContext {
  priorPhase: AppPhase;
  birthPhaseCommitted: boolean;
  activating: boolean;
  /** Operator reopened first-boot setup from Birth (credentials / fabric test). */
  setupReviewActive?: boolean;
}

function surfaceToPhase(surface: AppSurface): AppPhase {
  switch (surface) {
    case "setup":
      return "wizard";
    case "birth":
      return "birth";
    case "deck":
      return "cockpit";
  }
}

function birthReady(payload: OnboardingPayload): boolean {
  if (payload.birth.certificate_ok === false) {
    return false;
  }
  if (payload.birth.certificate_ok === true) {
    return true;
  }
  return payload.birth.artifacts_ok;
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
  return "cockpit";
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
    return surfaceToPhase(payload.app_surface);
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
  return legacySurfaceFallback(payload) === "cockpit";
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
    return "wizard";
  }
  if (priorPhase === "cockpit" || lastPayload?.app_surface === "deck") {
    return "cockpit";
  }
  if (priorPhase === "birth" || lastPayload?.app_surface === "birth") {
    return "birth";
  }
  return "wizard";
}
