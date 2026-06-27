import { lazy, Suspense, useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import { toast } from "sonner";

import { BirthCompletionSummary } from "@/components/birth/BirthCompletionSummary";
import { BirthDiagnosticsDrawer } from "@/components/birth/BirthDiagnosticsDrawer";
import { BirthFailureOverlayShell } from "@/components/birth/BirthFailureOverlayShell";
import { BirthPhasePulse } from "@/components/birth/BirthPhasePulse";
import { BirthRecoveryActionBar } from "@/components/birth/BirthRecoveryActionBar";
import { BirthOrganismVisual } from "@/components/birth/BirthOrganismVisual";
import { BirthRecoveryPanel } from "@/components/birth/BirthRecoveryPanel";
import { BirthRemediationBar } from "@/components/birth/BirthRemediationBar";
import { BirthStageScorecard } from "@/components/birth/BirthStageScorecard";
import { OnboardingShell } from "@/components/onboarding/OnboardingShell";
import { ModeTransitionVeil } from "@/components/cockpit/ModeTransitionVeil";
import { Button } from "@/components/ui/button";
import { useBirthPhaseMonitor } from "@/hooks/useBirthPhaseMonitor";
import { useDeckTransition } from "@/hooks/useDeckTransition";
import { useOnboardingModeMotion } from "@/hooks/useOnboardingModeMotion";
import { usePPOEvolution } from "@/hooks/usePPOEvolution";
import { usePrefersReducedMotion } from "@/hooks/usePrefersReducedMotion";
import { detectBirthRecoveryKind } from "@/lib/birthRecoveryModel";
import { isBirthInterrupted, isBirthStageStalled, resolveBirthPhaseCopy } from "@/lib/birthPhaseModel";
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
  const reuseDataBirth = useBirthStore((s) => s.reuseDataBirth);
  const resumeStalledStage = useBirthStore((s) => s.resumeStalledStage);
  const expandAndRetryStalledStage = useBirthStore((s) => s.expandAndRetryStalledStage);
  const targetTrades = useBirthStore((s) => s.targetTrades);
  const setPhase = useOnboardingStore((s) => s.setPhase);
  const completeBirthTransition = useOnboardingStore((s) => s.completeBirthTransition);
  const reducedMotion = usePrefersReducedMotion();
  const modeMotion = useOnboardingModeMotion();
  const [recoveryDismissed, setRecoveryDismissed] = useState(false);
  const [retrying, setRetrying] = useState(false);
  const [realPreviewActive, setRealPreviewActive] = useState(false);
  const [milestoneVeilActive, setMilestoneVeilActive] = useState(false);
  const veiledMilestonesRef = useRef<Set<string>>(new Set());
  const { transition, startTransition, completeTransition } = useDeckTransition();
  const awakening = uiPhase === "finale";
  const certificateFailed = uiPhase === "certificate_failed";
  const stageStalledActive =
    !awakening &&
    !recoveryDismissed &&
    (uiPhase === "stage_stalled" || isBirthStageStalled(status));
  const recoveryOverlayActive = certificateFailed || stageStalledActive;
  const failed = uiPhase === "error" || certificateFailed;
  const running = uiPhase === "running" && !stageStalledActive;
  const { logs, connected } = usePPOEvolution(!failed && !awakening);
  const recoveryKind = detectBirthRecoveryKind(status);
  const interrupted = status != null && isBirthInterrupted(status);
  const showRecovery =
    (Boolean(recoveryKind) || interrupted) &&
    !recoveryDismissed &&
    !failed &&
    !certificateFailed &&
    !stageStalledActive &&
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
      : stageStalledActive
        ? "stage_stalled"
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

  const handleResumeBirth = () => {
    setRetrying(true);
    void retryBirth()
      .then((ok) => {
        if (ok) {
          toast.success("Continuing birth from checkpoint");
          return;
        }
        toast.error(useBirthStore.getState().pollError ?? "Birth resume failed");
      })
      .finally(() => setRetrying(false));
  };

  const handleWipeRetryBirth = () => {
    setRetrying(true);
    void retryBirth({ wipe: true })
      .then((ok) => {
        if (ok) {
          toast.success("Fresh birth training started");
          return;
        }
        toast.error(useBirthStore.getState().pollError ?? "Birth restart failed");
      })
      .finally(() => setRetrying(false));
  };

  const handleReuseDataBirth = () => {
    setRetrying(true);
    void reuseDataBirth()
      .then((ok) => {
        if (ok) {
          toast.success("Resuming with reused data manifest");
          return;
        }
        toast.error(useBirthStore.getState().pollError ?? "Birth reuse failed");
      })
      .finally(() => setRetrying(false));
  };

  const handleResumeStalledStage = () => {
    setRetrying(true);
    void resumeStalledStage()
      .then((ok) => {
        if (ok) {
          toast.success("Resuming stalled curriculum stage");
          return;
        }
        toast.error(useBirthStore.getState().pollError ?? "Stage resume failed");
      })
      .finally(() => setRetrying(false));
  };

  const handleExpandAndRetryStalledStage = () => {
    setRetrying(true);
    void expandAndRetryStalledStage()
      .then((ok) => {
        if (ok) {
          toast.success("Expanding data and retrying stage");
          return;
        }
        toast.error(useBirthStore.getState().pollError ?? "Expand and retry failed");
      })
      .finally(() => setRetrying(false));
  };

  const handleWipeStalledStage = () => {
    setRetrying(true);
    void retryBirth({ wipe: true })
      .then((ok) => {
        if (ok) {
          toast.success("Fresh birth training started");
          return;
        }
        toast.error(useBirthStore.getState().pollError ?? "Birth restart failed");
      })
      .finally(() => setRetrying(false));
  };

  const stalledBlocker =
    String(status?.progress?.pass_reason ?? "").trim() ||
    String(status?.progress?.stage_blocker_metric ?? "").trim().replace(/_/g, " ");
  const adaptationTier = Math.max(0, Number(status?.progress?.adaptation_tier ?? 0) || 0);
  const maxAdaptationTiers = Math.max(1, Number(status?.progress?.max_adaptation_tiers ?? 4) || 4);
  const stalledRetries = Math.max(0, Number(status?.progress?.retries_this_stage ?? 0) || 0);
  const maxStageRetries = Math.max(1, Number(status?.progress?.max_stage_retries ?? 3) || 3);

  const certificateFailureDetail =
    (Array.isArray(status?.failure_reasons) && status.failure_reasons.length > 0
      ? status.failure_reasons.join(" · ")
      : null) ||
    status?.message ||
    status?.certificate_reason ||
    "Review OOS metrics below and choose a recovery action.";

  return (
    <OnboardingShell className="birth-phase-screen birth-phase-screen--cinematic">
      <motion.div
        className={cn(
          "birth-phase-cinematic relative mx-auto flex h-dvh min-h-0 w-full max-w-none flex-col overflow-hidden",
          recoveryOverlayActive && "birth-phase-cinematic--recovery-active",
        )}
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
              recoveryOverlayActive && "invisible opacity-0",
            )}
          >
            <div
              className={cn(
                "birth-phase-hud-band text-center",
                !recoveryOverlayActive && "pointer-events-auto",
              )}
            >
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
              {running && !failed && !awakening && status?.progress ? (
                <>
                  <BirthStageScorecard
                    progress={status.progress}
                    variant="compact"
                    className="mt-2"
                  />
                  <BirthRemediationBar status={status} className="mt-2 max-w-md mx-auto" />
                </>
              ) : null}
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
          <BirthFailureOverlayShell
            className="birth-phase-certificate-overlay z-40"
            title="Birth Certificate thresholds not met"
            subtitle={certificateFailureDetail}
            error={pollError}
            actions={
              <BirthRecoveryActionBar
                loading={retrying}
                actions={[
                  {
                    id: "continue",
                    label: "Continue learning",
                    loadingLabel: "Starting birth…",
                    variant: "primary",
                    onClick: handleResumeBirth,
                  },
                  {
                    id: "reuse",
                    label: "Reuse data & retry",
                    variant: "secondary",
                    onClick: handleReuseDataBirth,
                  },
                  {
                    id: "wipe",
                    label: "Wipe & restart",
                    variant: "outline",
                    onClick: handleWipeRetryBirth,
                  },
                  {
                    id: "setup",
                    label: "Return to setup",
                    variant: "ghost",
                    onClick: () => {
                      useBirthStore.getState().reset();
                      setPhase("wizard");
                    },
                  },
                ]}
              />
            }
          >
            <BirthCompletionSummary status={status} />
            <BirthRemediationBar status={status} />
          </BirthFailureOverlayShell>
        ) : null}

        {stageStalledActive ? (
          <BirthFailureOverlayShell
            title="Curriculum stage stalled"
            subtitle={phaseSubtitle}
            meta={
              stalledBlocker ? (
                <p className="mt-2 rounded border border-amber-500/30 bg-amber-950/20 px-3 py-2 font-mono text-xs text-amber-100">
                  Blocker: {stalledBlocker}
                </p>
              ) : null
            }
            error={pollError}
            actions={
              <BirthRecoveryActionBar
                loading={retrying}
                actions={[
                  {
                    id: "retry",
                    label: "Retry stage",
                    loadingLabel: "Starting…",
                    variant: "primary",
                    onClick: handleResumeStalledStage,
                  },
                  {
                    id: "expand",
                    label: "Expand & retry",
                    variant: "secondary",
                    onClick: handleExpandAndRetryStalledStage,
                  },
                  {
                    id: "wipe",
                    label: "Wipe & restart",
                    variant: "outline",
                    onClick: handleWipeStalledStage,
                  },
                  {
                    id: "dismiss",
                    label: "Dismiss",
                    variant: "ghost",
                    onClick: () => setRecoveryDismissed(true),
                  },
                ]}
              />
            }
          >
            <BirthStageScorecard progress={status?.progress} />
            <p className="text-center text-xs text-muted-foreground">
              Adaptive tier {adaptationTier + 1}/{maxAdaptationTiers} · retries {stalledRetries}/
              {maxStageRetries}
              {status?.engine_version ? ` · engine ${status.engine_version}` : ""}
            </p>
          </BirthFailureOverlayShell>
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
