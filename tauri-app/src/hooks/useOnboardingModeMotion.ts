import { useMemo } from "react";

import { usePrefersReducedMotion } from "@/hooks/usePrefersReducedMotion";
import { modeTransition } from "@/lib/modePresentation";

/** Onboarding and birth always use SIM motion regardless of persisted operator mode. */
export function useOnboardingModeMotion() {
  const reducedMotion = usePrefersReducedMotion();
  return useMemo(() => modeTransition("SIM", reducedMotion), [reducedMotion]);
}
