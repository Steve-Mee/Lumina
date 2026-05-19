import { motion } from "framer-motion";

import { OnboardingBrand } from "@/components/onboarding/OnboardingShell";
import { Button } from "@/components/ui/button";

import type { ReadinessRow } from "@/lib/onboardingSteps";

interface WelcomeStepProps {
  onContinue: () => void;
  shortPath?: boolean;
  readiness?: ReadinessRow[];
}

export function WelcomeStep({ onContinue, shortPath, readiness = [] }: WelcomeStepProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: shortPath ? 0.2 : 0.5 }}
      className="flex flex-col items-center gap-10 px-6 py-12"
    >
      <OnboardingBrand />
      <div className="onboarding-card max-w-lg p-6 text-center">
        <p className="text-sm leading-relaxed text-muted-foreground">
          {shortPath
            ? "Almost ready. Complete the remaining steps to activate Birth Phase and enter the Command Deck."
            : "Welcome aboard. We'll detect what's missing — backend, intelligence stack, credentials — and guide you through only what's needed."}
        </p>
        {readiness.length > 0 && !shortPath && (
          <p className="mt-3 text-xs text-cyan-300/80">
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
