import { lazy, Suspense, useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import { toast } from "sonner";

import { BirthCompletionSummary } from "@/components/birth/BirthCompletionSummary";
import { BirthDiagnosticsDrawer } from "@/components/birth/BirthDiagnosticsDrawer";
import { BirthPhasePulse } from "@/components/birth/BirthPhasePulse";
import { BirthOrganismVisual } from "@/components/birth/BirthOrganismVisual";
import { BirthRecoveryPanel } from "@/components/birth/BirthRecoveryPanel";
import { OnboardingShell } from "@/components/onboarding/OnboardingShell";
import { ModeTransitionVeil } from "@/components/cockpit/ModeTransitionVeil";
import { Button } from "@/components/ui/button";
import { useBirthPhaseMonitor } from "@/hooks/useBirthPhaseMonitor";
import { useDeckTransition } from "@/hooks/useDeckTransition";
import { useOnboardingModeMotion } from "@/hooks/useOnboardingModeMotion";
import { usePPOEvolution } from "@/hooks/usePPOEvolution";
import { usePrefersReducedMotion } from "@/hooks/usePrefersReducedMotion";
import { detectBirthRecoveryKind } from "@/lib/birthRecoveryModel";
import { isBirthInterrupted } from "@/lib/birthPhaseModel";
import { resolveBirthPhaseCopy } from "@/lib/birthPhaseModel";
import { transitionOrNone, springBirthLuxury } from "@/lib/motionPresets";
import {
  distressPanelClass,
  warnOverlayBodyClass,
  warnOverlayPanelClass,
  warnOverlayTitleClass,
} from "@/lib/modePresentation";
import { cn } from "@/lib/utils";
import {
  clearBirthForExtraTraining,
  startBirthSessionContinue,
  type BirthSettingsPayload,
} from "@/lib/birthClient";
import { stopBirth } from "@/lib/runtimeClient";
import { useBirthStore } from "@/store/birthStore";
import { useOnboardingStore } from "@/store/onboardingStore";

const BirthHelixVisual = lazy(() =>
  import("@/components/birth/BirthHelixVisual").then((module) => ({
    default: module.BirthHelixVisual,
  })),
);

export function BirthPhaseScreen() {
  useBirthPhaseMonitor();

  const headline = useBirthStore((s) => s.headline);
  const milestones = useBirthStore((s) => s.milestones);
  const status = useBirthStore((s) => s.status);
  const uiPhase = useBirthStore((s) => s.uiPhase);
  const pollError = useBirthStore((s) => s.pollError);
  const retryBirth = useBirthStore((s) => s.retryBirth);
  const targetTrades = useBirthStore((s) => s.targetTrades);
  const setPhase = useOnboardingStore((s) => s.setPhase);
  const completeBirthTransition = useOnboardingStore((s) => s.completeBirthTransition);
  const reducedMotion = usePrefersReducedMotion();
  const modeMotion = useOnboardingModeMotion();
  const awakening = uiPhase === "finale";
  const certificateFailed = uiPhase === "certificate_failed";
  const failed = uiPhase === "error" || certificateFailed;
  const running = uiPhase === "running";
  const { logs, connected } = usePPOEvolution(!failed && !awakening);
  const recoveryKind = detectBirthRecoveryKind(status);
  const interrupted = status != null && isBirthInterrupted(status);
  const [recoveryDismissed, setRecoveryDismissed] = useState(false);
  const [realPreviewActive, setRealPreviewActive] = useState(false);
  const [milestoneVeilActive, setMilestoneVeilActive] = useState(false);
  const veiledMilestonesRef = useRef<Set<string>>(new Set());
  const { transition, startTransition, completeTransition } = useDeckTransition();
  const showRecovery =
    (Boolean(recoveryKind) || interrupted) &&
    !recoveryDismissed &&
    !failed &&
    !certificateFailed &&
    !awakening;
  const trainingDraft = useOnboardingStore((s) => s.draft.training);

  const birthSettingsInitial: Partial<BirthSettingsPayload> = {
    training_trades: targetTrades,
    prefer_real_data_only: trainingDraft.prefer_real_data_only,
    max_real_days: trainingDraft.max_real_days,
    allow_minimal_synthetic_fallback: trainingDraft.allow_minimal_synthetic_fallback,
    require_real_simulator_data: trainingDraft.prefer_real_data_only,
  };

  const helixActivating = running || awakening;
  const birthMotion = { ...modeMotion, ...springBirthLuxury };
  const phaseSubtitle = resolveBirthPhaseCopy(
    certificateFailed
      ? "certificate_failed"
      : uiPhase === "error"
        ? "error"
        : awakening
          ? "finale"
          : running
            ? "running"
            : "idle",
    milestones,
  );

  useEffect(() => {
    if (!running || failed || awakening) {
      return;
    }
    for (const milestone of milestones) {
      if (
        (milestone.id === "refinement" ||
          milestone.id === "awakening" ||
          milestone.id === "strategies") &&
        milestone.state === "complete" &&
        !veiledMilestonesRef.current.has(milestone.id)
      ) {
        veiledMilestonesRef.current.add(milestone.id);
        setMilestoneVeilActive(true);
        break;
      }
    }
  }, [milestones, running, failed, awakening]);

  const handleStopBirth = () =>
    void stopBirth()
      .then(() => toast.success("Birth phase stopped"))
      .catch((e) => toast.error(e instanceof Error ? e.message : "Stop failed"));

  const enterCommandDeck = () => {
    setRealPreviewActive(true);
  };

  const onRealPreviewComplete = () => {
    setRealPreviewActive(false);
    startTransition({
      kind: "birthEntry",
      targetMode: "SIM",
      scopeSelector: ".onboarding-shell",
    });
  };

  const completeDeckEntry = () => {
    completeTransition();
    toast.success("Welcome to the Neural Command Deck");
    completeBirthTransition();
    useBirthStore.getState().reset();
  };

  return (
    <OnboardingShell className="birth-phase-screen birth-phase-screen--cinematic">
      <motion.div
        className="birth-phase-cinematic mx-auto flex h-dvh min-h-0 w-full max-w-none flex-col overflow-hidden"
        animate={{ opacity: transition.active ? 0.35 : 1 }}
        transition={transitionOrNone(reducedMotion, birthMotion)}
      >
        <motion.div
          className={cn(
            "birth-phase-hero relative flex min-h-0 flex-1 flex-col overflow-hidden",
            awakening && "birth-finale-lock",
          )}
          animate={{ scale: awakening ? 1.03 : 1 }}
          transition={transitionOrNone(reducedMotion, modeMotion)}
        >
          <div className="birth-phase-helix-stage flex min-h-0 flex-1 items-center justify-center">
            <Suspense
              fallback={
                <div className="flex h-full min-h-[50dvh] w-full items-center justify-center">
                  <BirthOrganismVisual className="size-48 opacity-80" />
                </div>
              }
            >
              <BirthHelixVisual
                activating={helixActivating}
                ceremonyMode
                trainingTrades={targetTrades}
                className="h-full min-h-[50dvh] w-full md:min-h-[60dvh]"
              />
            </Suspense>
          </div>

          <div
            className={cn(
              "birth-phase-hud pointer-events-none absolute inset-x-0 bottom-0 z-10 flex flex-col gap-2 px-4 pb-16 pt-4 md:px-6 md:pb-20 md:pt-6",
              awakening && "birth-phase-hud--finale",
            )}
          >
            <div className="birth-phase-hud-band pointer-events-auto text-center">
              <motion.h2
                className="birth-phase-headline text-2xl font-semibold tracking-wide md:text-4xl"
                key={awakening ? "finale-headline" : headline}
                initial={reducedMotion ? false : { opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={transitionOrNone(reducedMotion, birthMotion)}
              >
                {awakening ? "Birth complete" : headline}
              </motion.h2>
              <p className="birth-phase-subtitle mt-1 text-sm">
                {awakening
                  ? "Your organism is trained and ready for the command deck."
                  : phaseSubtitle}
              </p>
              {awakening ? (
                <p className="birth-phase-finale-note mt-2 text-sm">
                  Capital Protection mode awaits in the command deck.
                </p>
              ) : null}
            </div>

            {running && !failed && !awakening ? (
              <div className="birth-phase-hud-band pointer-events-none flex justify-center">
                <BirthPhasePulse
                  running={running}
                  milestones={milestones}
                  progress={status?.progress}
                />
              </div>
            ) : null}

            {awakening ? (
              <div className="birth-phase-hud-band birth-phase-hud-cta pointer-events-auto flex flex-wrap items-center justify-center gap-3 pt-2">
                <Button
                  type="button"
                  className="onboarding-cta min-w-[200px] py-5 text-base"
                  autoFocus
                  onClick={enterCommandDeck}
                >
                  Enter command deck
                </Button>
                <Button
                  type="button"
                  variant="link"
                  size="sm"
                  className="font-mono text-[10px] tracking-wide uppercase text-muted-foreground"
                  onClick={() =>
                    void clearBirthForExtraTraining()
                      .then(() => startBirthSessionContinue(targetTrades))
                      .then(() => {
                        useBirthStore.setState({ uiPhase: "running" });
                        toast.success("Extra training started from checkpoint");
                      })
                      .catch((e) =>
                        toast.error(e instanceof Error ? e.message : "Extra training failed"),
                      )
                  }
                >
                  Extra training
                </Button>
              </div>
            ) : null}
          </div>

          {!failed ? (
            <div className="birth-phase-ops pointer-events-none absolute inset-x-0 bottom-4 z-20 flex justify-center md:bottom-5">
              <BirthDiagnosticsDrawer
                running={running}
                finale={awakening}
                defaultOpen={awakening}
                milestones={milestones}
                progress={status?.progress}
                elapsedSeconds={status?.elapsed_seconds}
                progressMessage={status?.progress?.message ?? status?.message}
                birthStatus={status}
                settingsInitial={birthSettingsInitial}
                trainingLogs={logs}
                trainingConnected={connected}
                showStop={running && !awakening}
                onStop={handleStopBirth}
              />
            </div>
          ) : null}
        </motion.div>

        {showRecovery ? (
          <BirthRecoveryPanel
            status={status}
            targetTrades={targetTrades}
            className="relative z-30 mx-4 mb-2 shrink-0"
            onDismiss={() => setRecoveryDismissed(true)}
          />
        ) : null}

        {certificateFailed ? (
          <div className="relative z-30 mx-4 mb-4 shrink-0 space-y-3">
            <BirthCompletionSummary status={status} />
            <div
              className={cn(
                "birth-phase-certificate-failed rounded-xl p-4 text-sm lumina-glass lumina-glass--overlay",
                warnOverlayPanelClass(),
              )}
            >
              <p className={warnOverlayTitleClass()}>{headline}</p>
              <p className={cn("mt-1", warnOverlayBodyClass())}>
                {status?.certificate_reason ??
                  status?.message ??
                  "Birth Certificate v2 thresholds were not met. Review OOS metrics and retry."}
              </p>
              <div className="mt-4 flex flex-wrap gap-3">
                <Button type="button" className="onboarding-cta" onClick={() => void retryBirth()}>
                  Retry birth
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  className="text-muted-foreground"
                  onClick={() => {
                    useBirthStore.getState().reset();
                    setPhase("wizard");
                  }}
                >
                  Return to setup
                </Button>
              </div>
            </div>
          </div>
        ) : null}

        {uiPhase === "error" ? (
          <div
            className={cn(
              "birth-phase-error relative z-30 mx-4 mb-4 shrink-0 rounded-xl p-4 text-sm lumina-glass lumina-glass--overlay",
              warnOverlayPanelClass(),
            )}
          >
            <p className={warnOverlayTitleClass()}>Birth interrupted</p>
            <p className={cn("mt-1", warnOverlayBodyClass())}>
              {status?.error ?? status?.message ?? pollError ?? "Training could not continue."}
            </p>
            <div className="mt-4 flex flex-wrap gap-3">
              <Button type="button" className="onboarding-cta" onClick={() => void retryBirth()}>
                Retry birth
              </Button>
              <Button
                type="button"
                variant="ghost"
                className="text-muted-foreground"
                onClick={() => {
                  useBirthStore.getState().reset();
                  setPhase("wizard");
                }}
              >
                Return to setup
              </Button>
            </div>
          </div>
        ) : null}

        {pollError && !failed ? (
          <p
            className={cn(
              "relative z-30 mx-auto mb-3 max-w-md shrink-0 px-4 text-center text-xs",
              distressPanelClass("warn"),
            )}
          >
            {pollError}
          </p>
        ) : null}
      </motion.div>

      <ModeTransitionVeil
        active={milestoneVeilActive}
        targetMode="REAL"
        durationSec={0.85}
        scopeSelector=".onboarding-shell"
        onComplete={() => setMilestoneVeilActive(false)}
      />
      <ModeTransitionVeil
        active={realPreviewActive}
        targetMode="REAL"
        durationSec={1.2}
        scopeSelector=".onboarding-shell"
        onComplete={onRealPreviewComplete}
      />
      <ModeTransitionVeil
        active={transition.active}
        targetMode={transition.targetMode}
        durationSec={transition.durationSec}
        scopeSelector={transition.scopeSelector}
        onComplete={completeDeckEntry}
      />
    </OnboardingShell>
  );
}
