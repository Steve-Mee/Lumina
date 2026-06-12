import { useEffect, type ReactNode } from "react";

import { BirthPhaseScreen } from "@/components/birth/BirthPhaseScreen";
import { OnboardingWizard } from "@/components/onboarding/OnboardingWizard";
import { type AppPhase, useOnboardingStore } from "@/store/onboardingStore";
import { useBirthStore } from "@/store/birthStore";

interface OnboardingGateProps {
  children: (phase: Exclude<AppPhase, "wizard" | "birth">) => ReactNode;
}

export function OnboardingGate({ children }: OnboardingGateProps) {
  const phase = useOnboardingStore((s) => s.phase);
  const payload = useOnboardingStore((s) => s.payload);
  const trainingTrades = useOnboardingStore((s) => s.draft.training.training_trades);
  const refresh = useOnboardingStore((s) => s.refresh);
  const setPhase = useOnboardingStore((s) => s.setPhase);
  const setTargetTrades = useBirthStore((s) => s.setTargetTrades);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    if (payload?.app_surface !== "birth") {
      return;
    }
    setTargetTrades(trainingTrades);
    if (phase === "wizard") {
      setPhase("birth");
    }
  }, [payload?.app_surface, phase, setPhase, setTargetTrades, trainingTrades]);

  if (phase === "wizard") {
    return <OnboardingWizard />;
  }

  if (phase === "birth") {
    return <BirthPhaseScreen />;
  }

  return <>{children(phase)}</>;
}
