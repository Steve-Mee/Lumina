import { lazy, Suspense, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { CheckCircle2 } from "lucide-react";
import { toast } from "sonner";

import { BirthCompletionSummary } from "@/components/birth/BirthCompletionSummary";
import { BirthDiagnosticsDrawer } from "@/components/birth/BirthDiagnosticsDrawer";
import { BirthMetricsStrip } from "@/components/birth/BirthMetricsStrip";
import { BirthMilestoneTrack } from "@/components/birth/BirthMilestoneTrack";
import { BirthOrganismVisual } from "@/components/birth/BirthOrganismVisual";
import { BirthRecoveryPanel } from "@/components/birth/BirthRecoveryPanel";
import { OnboardingShell } from "@/components/onboarding/OnboardingShell";
import { ModeTransitionVeil } from "@/components/cockpit/ModeTransitionVeil";
import { Button } from "@/components/ui/button";
import { useBirthPhaseMonitor } from "@/hooks/useBirthPhaseMonitor";
import { useDeckTransition } from "@/hooks/useDeckTransition";
import { useModeMotion } from "@/hooks/useModeMotion";
import { usePPOEvolution } from "@/hooks/usePPOEvolution";
import { usePrefersReducedMotion } from "@/hooks/usePrefersReducedMotion";
import { detectBirthRecoveryKind } from "@/lib/birthRecoveryModel";
import { transitionOrNone, springBirthLuxury } from "@/lib/motionPresets";
import { modeTitleClass, modeValueClass, distressPanelClass, warnOverlayBodyClass, warnOverlayPanelClass, warnOverlayTitleClass } from "@/lib/modePresentation";
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
  const modeMotion = useModeMotion();
  const awakening = uiPhase === "finale";
  const failed = uiPhase === "error";
  const running = uiPhase === "running";
  const { logs, connected } = usePPOEvolution(!failed && !awakening);
  const recoveryKind = detectBirthRecoveryKind(status);
  const [recoveryDismissed, setRecoveryDismissed] = useState(false);
  const { transition, startTransition, completeTransition } = useDeckTransition();
  const showRecovery = Boolean(recoveryKind) && !recoveryDismissed && !failed && !awakening;
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

  const enterCommandDeck = () => {
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
        className="birth-phase-cinematic mx-auto flex min-h-screen w-full max-w-5xl flex-col px-4 py-8 md:py-10"
        animate={{ opacity: transition.active ? 0.35 : 1 }}
        transition={transitionOrNone(reducedMotion, birthMotion)}
      >
        <motion.div
          className="birth-phase-hero relative mb-4 min-h-[300px] flex-1 md:min-h-[360px]"
          animate={{ scale: awakening ? 1.05 : 1 }}
          transition={transitionOrNone(reducedMotion, modeMotion)}
        >
          <Suspense
            fallback={
              <div className="flex h-full min-h-[300px] items-center justify-center">
                <BirthOrganismVisual className="size-48 opacity-80" />
              </div>
            }
          >
            <BirthHelixVisual
              activating={helixActivating}
              trainingTrades={targetTrades}
              className="min-h-[300px] md:min-h-[360px]"
            />
          </Suspense>
          <div className="birth-phase-vignette pointer-events-none" aria-hidden />

          <div className="birth-phase-hud lumina-glass lumina-glass--hud pointer-events-none absolute inset-x-0 bottom-0 z-10 flex flex-col gap-2 p-4 md:p-6">
            <div className="birth-phase-hud-band pointer-events-auto text-center">
              <motion.h2
                className="birth-phase-headline text-2xl font-semibold tracking-wide md:text-4xl"
                key={headline}
                initial={reducedMotion ? false : { opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.35 }}
              >
                {headline}
              </motion.h2>
              <p className="birth-phase-subtitle mt-1 text-sm">
                {awakening
                  ? "Birth phase complete — continue training or enter the command deck."
                  : "Neural lattice forming — DNA, strategies, and policy in parallel."}
              </p>
            </div>
            {!failed && !awakening ? (
              <div className="birth-phase-hud-band pointer-events-auto">
                {running && status?.progress ? (
                  <BirthMetricsStrip
                    progress={status?.progress}
                    elapsedSeconds={status?.elapsed_seconds}
                    message={status?.progress?.message ?? status?.message}
                  />
                ) : (
                  <BirthMilestoneTrack
                    milestones={milestones}
                    className="birth-phase-milestones max-sm:scale-90 max-sm:origin-bottom"
                  />
                )}
              </div>
            ) : null}
          </div>

          {!failed && !awakening ? (
            <div className="absolute top-3 right-3 z-20">
              <BirthDiagnosticsDrawer
                running={running}
                settingsInitial={birthSettingsInitial}
                trainingLogs={logs}
                trainingConnected={connected}
              />
            </div>
          ) : null}
        </motion.div>

        {showRecovery ? (
          <BirthRecoveryPanel
            status={status}
            targetTrades={targetTrades}
            className="mb-4"
            onDismiss={() => setRecoveryDismissed(true)}
          />
        ) : null}

        {!failed ? (
          <AnimatePresence mode="wait">
            {!awakening ? (
              <motion.div
                key="birth-ops"
                className="birth-phase-ops flex flex-col items-center gap-3"
                initial={false}
                exit={reducedMotion ? undefined : { opacity: 0, y: -8 }}
                transition={transitionOrNone(reducedMotion, modeMotion)}
              >
                <Button
                  type="button"
                  variant="command-ghost"
                  size="sm"
                  className="font-mono text-[10px] tracking-wide uppercase"
                  onClick={() =>
                    void stopBirth()
                      .then(() => toast.success("Birth phase stopped"))
                      .catch((e) =>
                        toast.error(e instanceof Error ? e.message : "Stop failed"),
                      )
                  }
                >
                  Stop birth phase
                </Button>
              </motion.div>
            ) : (
              <motion.div
                key="birth-finale"
                className="birth-finale-hero overflow-hidden rounded-xl border border-cyan-400/25 lumina-glass lumina-glass--overlay"
                initial={reducedMotion ? false : { opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                transition={transitionOrNone(reducedMotion, { ...birthMotion, delay: 0.15 })}
              >
                <div className="border-b border-cyan-400/15 bg-cyan-500/8 px-6 py-5 text-center">
                  <CheckCircle2 className="mx-auto mb-3 size-12 text-cyan-300" />
                  <h3 className={cn("text-lg font-semibold", modeTitleClass("SIM"))}>Birth complete</h3>
                  <p className="mt-1 text-sm text-muted-foreground">
                    Your organism is trained and ready for the command deck.
                  </p>
                  <p className="mt-2 text-sm text-[#c9b896]/85">
                    Capital Protection mode awaits in the command deck.
                  </p>
                </div>
                <div className="px-6 pt-4">
                  <BirthCompletionSummary status={status} />
                </div>
                <div className="grid gap-3 px-6 py-4 text-center sm:grid-cols-3">
                  <div className="rounded-lg lumina-glass lumina-glass--panel px-3 py-2">
                    <p className="font-mono text-[9px] uppercase text-muted-foreground">Progress</p>
                    <p className={cn("mt-1 font-mono text-sm", modeValueClass("SIM"))}>
                      {status?.progress?.progress_pct != null
                        ? `${Math.round(status.progress.progress_pct)}%`
                        : status?.progress_pct != null
                          ? `${Math.round(status.progress_pct)}%`
                          : "100%"}
                    </p>
                  </div>
                  <div className="rounded-lg lumina-glass lumina-glass--panel px-3 py-2">
                    <p className="font-mono text-[9px] uppercase text-muted-foreground">Elapsed</p>
                    <p className={cn("mt-1 font-mono text-sm", modeValueClass("SIM"))}>
                      {status?.elapsed_seconds != null
                        ? `${Math.floor(status.elapsed_seconds / 60)}m ${status.elapsed_seconds % 60}s`
                        : "—"}
                    </p>
                  </div>
                  <div className="rounded-lg lumina-glass lumina-glass--panel px-3 py-2">
                    <p className="font-mono text-[9px] uppercase text-muted-foreground">Milestones</p>
                    <p className={cn("mt-1 font-mono text-sm", modeValueClass("SIM"))}>
                      {milestones.filter((m) => m.state === "complete").length}/{milestones.length}
                    </p>
                  </div>
                </div>
                <div className="flex flex-wrap justify-center gap-3 px-6 pb-6">
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
                    variant="secondary"
                    size="sm"
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
              </motion.div>
            )}
          </AnimatePresence>
        ) : (
          <div className={cn("birth-phase-error rounded-xl p-4 text-sm lumina-glass lumina-glass--overlay", warnOverlayPanelClass())}>
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
        )}

        {pollError && !failed ? (
          <p className={cn("mx-auto mt-4 max-w-md text-center text-xs", distressPanelClass("warn"))}>
            {pollError}
          </p>
        ) : null}
      </motion.div>

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
