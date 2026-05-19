import { useState } from "react";
import { motion } from "framer-motion";
import { CheckCircle2 } from "lucide-react";
import { toast } from "sonner";

import { BirthMetricsStrip } from "@/components/birth/BirthMetricsStrip";
import { BirthMilestoneTrack } from "@/components/birth/BirthMilestoneTrack";
import { BirthOrganismVisual } from "@/components/birth/BirthOrganismVisual";
import { BirthRecoveryPanel } from "@/components/birth/BirthRecoveryPanel";
import { PPOEvolutionDashboard } from "@/components/ppo/PPOEvolutionDashboard";
import { TrainingControlBar } from "@/components/operations/TrainingControlBar";
import { OnboardingBrand, OnboardingShell } from "@/components/onboarding/OnboardingShell";
import { Button } from "@/components/ui/button";
import { useBirthPhaseMonitor } from "@/hooks/useBirthPhaseMonitor";
import { usePPOEvolution } from "@/hooks/usePPOEvolution";
import { usePrefersReducedMotion } from "@/hooks/usePrefersReducedMotion";
import { detectBirthRecoveryKind } from "@/lib/birthRecoveryModel";
import { cn } from "@/lib/utils";
import {
  clearBirthForExtraTraining,
  startBirthSessionContinue,
} from "@/lib/birthClient";
import { stopBirth } from "@/lib/runtimeClient";
import { useBirthStore } from "@/store/birthStore";
import { useOnboardingStore } from "@/store/onboardingStore";

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
  const awakening = uiPhase === "finale";
  const failed = uiPhase === "error";
  const { logs, connected } = usePPOEvolution(!failed && !awakening);
  const showPpoDashboard = connected || logs.length > 0;
  const recoveryKind = detectBirthRecoveryKind(status);
  const [recoveryDismissed, setRecoveryDismissed] = useState(false);
  const showRecovery = Boolean(recoveryKind) && !recoveryDismissed && !failed && !awakening;

  return (
    <OnboardingShell className="birth-phase-screen">
      <div className="flex min-h-screen flex-col items-center justify-center px-4 py-10">
        <motion.div
          className={cn(
            "birth-phase-panel onboarding-card w-full px-6 py-8 md:px-10 md:py-10",
            showPpoDashboard ? "max-w-4xl" : "max-w-2xl",
          )}
          initial={reducedMotion ? false : { opacity: 0, scale: 0.98 }}
          animate={{ opacity: 1, scale: awakening ? 1.02 : 1 }}
          transition={{ duration: reducedMotion ? 0 : 0.5 }}
        >
          <div className="mb-8 text-center">
            <OnboardingBrand />
          </div>

          <BirthOrganismVisual awakening={awakening} className="mb-8" />

          <motion.h2
            className="birth-phase-headline mb-2 text-center text-xl font-semibold tracking-wide md:text-2xl"
            key={headline}
            initial={reducedMotion ? false : { opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.35 }}
          >
            {headline}
          </motion.h2>

          <p className="mb-8 text-center text-sm text-muted-foreground">
            {awakening
              ? "Birth phase complete — continue training or enter the command deck."
              : "Organism is being born… training DNA, strategies, and policy in parallel."}
          </p>

          <BirthMilestoneTrack milestones={milestones} className="mb-8" />

          {showRecovery ? (
            <BirthRecoveryPanel
              status={status}
              targetTrades={targetTrades}
              className="mb-6"
              onDismiss={() => setRecoveryDismissed(true)}
            />
          ) : null}

          {!failed ? (
            <>
              <BirthMetricsStrip
                progress={status?.progress}
                elapsedSeconds={status?.elapsed_seconds}
                message={status?.progress?.message ?? status?.message}
              />
              {showPpoDashboard ? (
                <PPOEvolutionDashboard
                  logs={logs}
                  connected={connected}
                  title="PPO Evolution Dashboard"
                  compact
                  className="mt-6"
                />
              ) : null}
              {!awakening ? (
                <div className="mt-6 flex flex-col items-center gap-3">
                  <TrainingControlBar compact className="justify-center" />
                  <Button
                    type="button"
                    variant="secondary"
                    size="sm"
                    onClick={() =>
                      void stopBirth()
                        .then(() => toast.success("Birth phase stopped"))
                        .catch((e) => toast.error(e instanceof Error ? e.message : "Stop failed"))
                    }
                  >
                    Stop birth phase
                  </Button>
                </div>
              ) : (
                <motion.div
                  className="birth-finale-hero mt-8 overflow-hidden rounded-xl border border-emerald-500/35 bg-emerald-950/25"
                  initial={reducedMotion ? false : { opacity: 0, y: 12 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.45 }}
                >
                  <div className="border-b border-emerald-500/20 bg-emerald-500/10 px-6 py-5 text-center">
                    <CheckCircle2 className="mx-auto mb-3 size-12 text-emerald-300" />
                    <h3 className="text-lg font-semibold text-emerald-100">Birth complete</h3>
                    <p className="mt-1 text-sm text-emerald-100/75">
                      Your organism is trained and ready for the command deck.
                    </p>
                  </div>
                  <div className="grid gap-3 px-6 py-4 text-center sm:grid-cols-3">
                    <div className="rounded-lg border border-white/10 bg-black/20 px-3 py-2">
                      <p className="font-mono text-[9px] uppercase text-muted-foreground">Progress</p>
                      <p className="mt-1 font-mono text-sm text-cyan-100">
                        {status?.progress?.progress_pct != null
                          ? `${Math.round(status.progress.progress_pct)}%`
                          : status?.progress_pct != null
                            ? `${Math.round(status.progress_pct)}%`
                            : "100%"}
                      </p>
                    </div>
                    <div className="rounded-lg border border-white/10 bg-black/20 px-3 py-2">
                      <p className="font-mono text-[9px] uppercase text-muted-foreground">Elapsed</p>
                      <p className="mt-1 font-mono text-sm text-cyan-100">
                        {status?.elapsed_seconds != null
                          ? `${Math.floor(status.elapsed_seconds / 60)}m ${status.elapsed_seconds % 60}s`
                          : "—"}
                      </p>
                    </div>
                    <div className="rounded-lg border border-white/10 bg-black/20 px-3 py-2">
                      <p className="font-mono text-[9px] uppercase text-muted-foreground">Milestones</p>
                      <p className="mt-1 font-mono text-sm text-cyan-100">
                        {milestones.filter((m) => m.state === "complete").length}/{milestones.length}
                      </p>
                    </div>
                  </div>
                  <div className="flex flex-wrap justify-center gap-3 px-6 pb-6">
                    <Button
                      type="button"
                      className="onboarding-cta min-w-[200px] py-5 text-base"
                      autoFocus
                      onClick={() => {
                        toast.success("Welcome to the Neural Command Deck");
                        completeBirthTransition();
                        useBirthStore.getState().reset();
                      }}
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
                      Extra trainen
                    </Button>
                  </div>
                </motion.div>
              )}
            </>
          ) : (
            <>
              <BirthRecoveryPanel status={status} targetTrades={targetTrades} className="mb-4" />
            <div className="birth-phase-error rounded-lg border border-red-500/30 bg-red-950/30 p-4 text-sm">
              <p className="font-medium text-red-200">Birth interrupted</p>
              <p className="mt-1 text-red-200/80">
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
            </>
          )}

          {pollError && !failed ? (
            <p className="mt-4 text-center text-xs text-amber-300/80">{pollError}</p>
          ) : null}
        </motion.div>
      </div>
    </OnboardingShell>
  );
}
