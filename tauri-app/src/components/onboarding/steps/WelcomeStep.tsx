import { motion } from "framer-motion";

import { OnboardingBrand } from "@/components/onboarding/OnboardingShell";
import { Button } from "@/components/ui/button";
import { useOnboardingModeMotion } from "@/hooks/useOnboardingModeMotion";
import { usePrefersReducedMotion } from "@/hooks/usePrefersReducedMotion";
import { transitionOrNone } from "@/lib/motionPresets";

import type { ReadinessRow } from "@/lib/onboardingSteps";

interface WelcomeStepProps {
  onContinue: () => void;
  shortPath?: boolean;
  readiness?: ReadinessRow[];
}

export function WelcomeStep({ onContinue, shortPath, readiness = [] }: WelcomeStepProps) {
  const reducedMotion = usePrefersReducedMotion();
  const modeMotion = useOnboardingModeMotion();

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={transitionOrNone(
        reducedMotion,
        shortPath ? { ...modeMotion, duration: 0.2 } : modeMotion,
      )}
      className="flex flex-col items-center gap-10 px-6 py-12"
    >
      <OnboardingBrand />
      <div className="welcome-card--organism relative lumina-glass lumina-glass--overlay max-w-lg p-6 text-center">
        <div className="t1-vignette pointer-events-none absolute inset-0 rounded-[inherit]" aria-hidden />
        <p className="relative text-sm leading-relaxed text-muted-foreground">
          {shortPath
            ? "Almost ready. Complete the remaining steps to activate Birth Phase and enter the Command Deck."
            : "Welcome aboard. We'll detect what's missing — backend, intelligence stack, credentials — and guide you through only what's needed."}
        </p>
        {readiness.length > 0 && !shortPath && (
          <p className="relative mt-3 text-xs text-cyan-300/80">
            {readiness.filter((row) => row.status === "missing").length} components still need attention.
          </p>
        )}
      </div>
      <Button className="onboarding-cta px-10 py-6 text-sm" onClick={onContinue}>
        Begin Setup
      </Button>
    </motion.div>
  );
}
