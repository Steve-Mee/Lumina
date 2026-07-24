import { useEffect, type ReactNode } from "react";

import { BirthPhaseScreen } from "@/components/birth/BirthPhaseScreen";
import { OnboardingWizard } from "@/components/onboarding/OnboardingWizard";
import { PlaygroundEnvelopeSeal } from "@/components/onboarding/PlaygroundEnvelopeSeal";
import { type AppPhase, useOnboardingStore } from "@/store/onboardingStore";
import { useBirthStore } from "@/store/birthStore";

interface OnboardingGateProps {
  children: (phase: Exclude<AppPhase, "wizard" | "birth">) => ReactNode;
}

export function OnboardingGate({ children }: OnboardingGateProps) {
  const phase = useOnboardingStore((s) => s.phase);
  const payload = useOnboardingStore((s) => s.payload);
  const trainingTrades = useOnboardingStore((s) => s.draft.training.training_trades);
  const setupReviewActive = useOnboardingStore((s) => s.setupReviewActive);
  const refresh = useOnboardingStore((s) => s.refresh);
  const setPhase = useOnboardingStore((s) => s.setPhase);
  const setTargetTrades = useBirthStore((s) => s.setTargetTrades);

  const needsEnvelopeSeal =
    phase === "cockpit" &&
    payload?.app_surface === "deck" &&
    payload.sim_envelope_sealed === false;

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    if (payload?.app_surface !== "birth") {
      return;
    }
    setTargetTrades(trainingTrades);
    // Allow operator-driven setup review (credentials / Fabric test) without kick-back.
    if (setupReviewActive) {
      return;
    }
    if (phase === "wizard") {
      setPhase("birth");
    }
  }, [
    payload?.app_surface,
    phase,
    setPhase,
    setTargetTrades,
    trainingTrades,
    setupReviewActive,
  ]);

  if (phase === "wizard") {
    return <OnboardingWizard />;
  }

  if (phase === "birth") {
    return <BirthPhaseScreen />;
  }

  if (needsEnvelopeSeal) {
    return <PlaygroundEnvelopeSeal />;
  }

  return <>{children(phase)}</>;
}
