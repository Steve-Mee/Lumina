import { useEffect, useRef, type ReactNode } from "react";

import { BirthPhaseScreen } from "@/components/birth/BirthPhaseScreen";
import { ApprenticeshipPhaseScreen } from "@/components/maturity/ApprenticeshipPhaseScreen";
import { AwakeningPhaseScreen } from "@/components/maturity/AwakeningPhaseScreen";
import { ProvingGroundPhaseScreen } from "@/components/maturity/ProvingGroundPhaseScreen";
import { PhaseHubScreen } from "@/components/maturity/PhaseHubScreen";
import { OnboardingWizard } from "@/components/onboarding/OnboardingWizard";
import { PlaygroundPhaseScreen } from "@/components/maturity/PlaygroundPhaseScreen";
import { PlaygroundEnvelopeSeal } from "@/components/onboarding/PlaygroundEnvelopeSeal";
import { ColdStartReadiness } from "@/components/startup/ColdStartReadiness";
import { NinjaTraderDegradedBanner } from "@/components/startup/NinjaTraderDegradedBanner";
import { birthExitKeepsPhaseHub } from "@/lib/awakening/awakeningStartHandoff";
import { shouldHoldStartupCover } from "@/lib/startupReadinessModel";
import { rememberOperatorPhase } from "@/lib/systemsGoSession";
import { type AppPhase, useOnboardingStore } from "@/store/onboardingStore";
import { useBirthStore } from "@/store/birthStore";

interface OnboardingGateProps {
  children: (phase: Exclude<AppPhase, "wizard" | "birth" | "hub" | "awakening" | "playground" | "apprenticeship" | "proving_ground">) => ReactNode;
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
  const activating = useOnboardingStore((s) => s.activating);
  const setTargetTrades = useBirthStore((s) => s.setTargetTrades);
  const birthUiPhase = useBirthStore((s) => s.uiPhase);
  const birthStatusName = useBirthStore((s) => s.status?.status);
  const birthStatusMessage = useBirthStore((s) => s.status?.message);
  const handoffStarted = useRef(false);
  const foundationHandoffStarted = useRef(false);

  const birthExitHandoff =
    phase === "birth" &&
    !activating &&
    !setupReviewActive &&
    birthExitKeepsPhaseHub({
      birthExitOk: payload?.birth.birth_exit_ok,
      birthUiPhase,
    });

  const needsEnvelopeSeal =
    phase === "cockpit" &&
    (payload?.app_surface === "deck" || payload?.app_surface === "hub") &&
    payload.sim_envelope_sealed === false &&
    operatorDeckActive;

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    rememberOperatorPhase(phase);
  }, [phase]);

  // Cover already lifted, but the first onboarding read has not landed.
  // Keep asking. A living eval answers in bursts; one timeout is not a dead app.
  useEffect(() => {
    if (!ntStartupResolved || phase !== "loading") return;
    let pending = false;
    const id = window.setInterval(() => {
      if (pending) return;
      pending = true;
      void refresh().finally(() => {
        pending = false;
      });
    }, 12_000);
    return () => window.clearInterval(id);
  }, [ntStartupResolved, phase, refresh]);

  useEffect(() => {
    if (!birthExitHandoff || handoffStarted.current) return;
    handoffStarted.current = true;
    useOnboardingStore.setState({ birthPhaseCommitted: false });
    void refresh();
  }, [birthExitHandoff, refresh]);

  // Full wipe / Wipe Birth closes the exit. A leftover finale must not keep
  // Phase Hub in front of the Genesis charter.
  useEffect(() => {
    if (payload?.birth.birth_exit_ok !== false) return;
    if (birthUiPhase !== "finale") return;
    const top = String(birthStatusName ?? "").toLowerCase();
    if (top === "completed") return;
    useBirthStore.getState().returnToGenesis();
  }, [payload?.birth.birth_exit_ok, birthUiPhase, birthStatusName]);

  // Five green stages leave a completed Birth status before the next onboarding
  // read. Stay on Genesis only for a real failure — a finished Foundation opens
  // Phase Hub, where Awakening starts.
  useEffect(() => {
    const top = String(birthStatusName ?? "").toLowerCase();
    const msg = String(birthStatusMessage ?? "");
    const foundationDone = top === "completed" || /foundation complete/i.test(msg);
    if (!foundationDone || foundationHandoffStarted.current || activating || setupReviewActive) {
      return;
    }
    if (phase === "hub" && payload?.birth.birth_exit_ok === true) return;
    foundationHandoffStarted.current = true;
    useBirthStore.setState({ genesisPinned: false, runPinned: false, uiPhase: "idle" });
    useOnboardingStore.setState({ birthPhaseCommitted: false });
    void refresh();
  }, [
    birthStatusName,
    birthStatusMessage,
    activating,
    setupReviewActive,
    phase,
    payload?.birth.birth_exit_ok,
    refresh,
  ]);

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

  // Cold-start cover until Systems Go commits this session.
  // Backend unreachable stays on the cover (retry lives there). Never unmount
  // ColdStart over Birth/Wizard — that stacks screens and resizes the window.
  const holdForNtGate = shouldHoldStartupCover(ntStartupResolved);

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
    if (!birthExitHandoff) {
      return (
        <>
          <BirthPhaseScreen />
          <NinjaTraderDegradedBanner />
        </>
      );
    }
    // Birth exit charter is Phase Hub. Awakening training starts from there.
    return (
      <>
        <PhaseHubScreen />
        <NinjaTraderDegradedBanner />
      </>
    );
  }

  if (phase === "awakening") {
    return (
      <>
        <AwakeningPhaseScreen />
        <NinjaTraderDegradedBanner />
      </>
    );
  }

  if (phase === "playground") {
    if (payload?.sim_envelope_sealed === false) {
      return <PlaygroundEnvelopeSeal />;
    }
    return (
      <>
        <PlaygroundPhaseScreen />
        <NinjaTraderDegradedBanner />
      </>
    );
  }

  if (phase === "apprenticeship") {
    return (
      <>
        <ApprenticeshipPhaseScreen />
        <NinjaTraderDegradedBanner />
      </>
    );
  }

  if (phase === "proving_ground") {
    return (
      <>
        <ProvingGroundPhaseScreen />
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
