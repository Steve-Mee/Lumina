import { useEffect, type ReactNode } from "react";

import { OnboardingWizard } from "@/components/onboarding/OnboardingWizard";
import { useOnboardingStore } from "@/store/onboardingStore";

interface OnboardingGateProps {
  children: (phase: "loading" | "wizard" | "cockpit") => ReactNode;
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

  return <>{children(phase)}</>;
}
