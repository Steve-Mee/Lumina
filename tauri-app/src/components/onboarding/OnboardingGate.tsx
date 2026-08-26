import { useEffect, type ReactNode } from "react";

import { BirthPhaseScreen } from "@/components/birth/BirthPhaseScreen";
import { PhaseHubScreen } from "@/components/maturity/PhaseHubScreen";
import { OnboardingWizard } from "@/components/onboarding/OnboardingWizard";
import { PlaygroundEnvelopeSeal } from "@/components/onboarding/PlaygroundEnvelopeSeal";
import { ColdStartReadiness } from "@/components/startup/ColdStartReadiness";
import { NinjaTraderDegradedBanner } from "@/components/startup/NinjaTraderDegradedBanner";
import { type AppPhase, useOnboardingStore } from "@/store/onboardingStore";
import { useBirthStore } from "@/store/birthStore";

interface OnboardingGateProps {
  children: (phase: Exclude<AppPhase, "wizard" | "birth" | "hub">) => ReactNode;
}

export function OnboardingGate({ children }: OnboardingGateProps) {
  const phase = useOnboardingStore((s) => s.phase);
  const payload = useOnboardingStore((s) => s.payload);
  const trainingTrades = useOnboardingStore((s) => s.draft.training.training_trades);
  const setupReviewActive = useOnboardingStore((s) => s.setupReviewActive);
  const operatorDeckActive = useOnboardingStore((s) => s.operatorDeckActive);
  const ntStartupResolved = useOnboardingStore((s) => s.ntStartupResolved);
  const refresh = useOnboardingStore((s) => s.refresh);
  const setPhase = useOnboardingStore((s) => s.setPhase);
  const setTargetTrades = useBirthStore((s) => s.setTargetTrades);

  const needsEnvelopeSeal =
    phase === "cockpit" &&
    (payload?.app_surface === "deck" || payload?.app_surface === "hub") &&
    payload.sim_envelope_sealed === false &&
    operatorDeckActive;

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

  // Cold-start cover until SSOT fetch completes.
  // NT process gate also holds the cover after SSOT maps phase — unless operator deferred.
  // Exception: when backend is unreachable, keep cover for backend retry (payload null or !reachable)
  // without requiring NT first (NT gate runs once backend is reachable).
  const backendReachable = payload?.backend.reachable === true;
  const holdForNtGate =
    !ntStartupResolved &&
    (phase === "loading" || backendReachable || payload == null);

  if (holdForNtGate) {
    return <ColdStartReadiness />;
  }

  if (phase === "wizard") {
    return (
      <>
        <OnboardingWizard />
        <NinjaTraderDegradedBanner />
      </>
    );
  }

  if (phase === "birth") {
    return (
      <>
        <BirthPhaseScreen />
        <NinjaTraderDegradedBanner />
      </>
    );
  }

  if (phase === "hub") {
    return (
      <>
        <PhaseHubScreen />
        <NinjaTraderDegradedBanner />
      </>
    );
  }

  if (needsEnvelopeSeal) {
    return <PlaygroundEnvelopeSeal />;
  }

  return (
    <>
      {children(phase)}
      <NinjaTraderDegradedBanner />
    </>
  );
}
