import { useEffect, type ReactNode } from "react";

import { BirthPhaseScreen } from "@/components/birth/BirthPhaseScreen";
import { OnboardingWizard } from "@/components/onboarding/OnboardingWizard";
import { type AppPhase, useOnboardingStore } from "@/store/onboardingStore";

interface OnboardingGateProps {
  children: (phase: Exclude<AppPhase, "wizard" | "birth">) => ReactNode;
}

export function OnboardingGate({ children }: OnboardingGateProps) {
  const phase = useOnboardingStore((s) => s.phase);
  const refresh = useOnboardingStore((s) => s.refresh);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  if (phase === "wizard") {
    return <OnboardingWizard />;
  }

  if (phase === "birth") {
    return <BirthPhaseScreen />;
  }

  return <>{children(phase)}</>;
}
