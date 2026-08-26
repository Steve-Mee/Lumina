/**
 * Suppress sonner toasts while cold-start readiness cover is visible.
 * Prefer step rows on StartupReadinessScreen over toast storms.
 */
import { toast } from "sonner";

import { useOnboardingStore } from "@/store/onboardingStore";

export function isStartupReadinessActive(): boolean {
  return useOnboardingStore.getState().phase === "loading";
}

/** toast.message that no-ops during cold-start readiness. */
export function startupSafeToastMessage(message: string): void {
  if (isStartupReadinessActive()) return;
  toast.message(message);
}

/** toast.error that no-ops during cold-start readiness (errors still set on store). */
export function startupSafeToastError(message: string): void {
  if (isStartupReadinessActive()) return;
  toast.error(message);
}
