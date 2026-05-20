import { usePrefersReducedMotion } from "@/hooks/usePrefersReducedMotion";
import { modeTransition } from "@/lib/modePresentation";
import { selectCurrentMode, useCoreStore } from "@/store/coreStore";

/** Mode-aware framer-motion transition (REAL = slower, calmer). */
export function useModeMotion(luxury = false) {
  const mode = useCoreStore(selectCurrentMode);
  const reducedMotion = usePrefersReducedMotion();
  return modeTransition(mode, reducedMotion, luxury);
}
