import { lazy, Suspense, useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import { toast } from "sonner";

import { BirthCommandBar } from "@/components/birth/BirthCommandBar";
import type { BirthAdvancedSection } from "@/components/birth/BirthAdvancedPanel";
import { BirthCompletionSummary } from "@/components/birth/BirthCompletionSummary";
import { BirthCinematicLayout } from "@/components/birth/BirthCinematicLayout";
import { BirthFailureOverlayShell } from "@/components/birth/BirthFailureOverlayShell";
import { BirthGenesisDeck } from "@/components/birth/BirthGenesisDeck";
import { BirthMissionControl } from "@/components/birth/BirthMissionControl";
import { BirthStageIntelColumn } from "@/components/birth/BirthStageIntelColumn";
import { BirthOrganismVisual } from "@/components/birth/BirthOrganismVisual";
import { BirthRecoveryActionBar } from "@/components/birth/BirthRecoveryActionBar";
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
import { detectBirthRecoveryKind, hasBirthCheckpointProgress, shouldAutoResumeBirth } from "@/lib/birthRecoveryModel";
import { isBirthEngineActive, isBirthInterrupted, isBirthStageStalled, resolveBirthPhaseCopy } from "@/lib/birthPhaseModel";
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
  startBirthSession,
  startBirthSessionContinue,
  wipeAllBirthData,
  type BirthSettingsPayload,
} from "@/lib/birthClient";
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
  const birthSurface = useBirthStore((s) => s.birthSurface);
  const poll = useBirthStore((s) => s.poll);
  const setBirthSurface = useBirthStore((s) => s.setBirthSurface);
  const pollError = useBirthStore((s) => s.pollError);
  const retryBirth = useBirthStore((s) => s.retryBirth);
  const reuseDataBirth = useBirthStore((s) => s.reuseDataBirth);
  const resumeStalledStage = useBirthStore((s) => s.resumeStalledStage);
  const expandAndRetryStalledStage = useBirthStore((s) => s.expandAndRetryStalledStage);
  const targetTrades = useBirthStore((s) => s.targetTrades);
  const setPhase = useOnboardingStore((s) => s.setPhase);
  const activateBirth = useOnboardingStore((s) => s.activateBirth);
  const activating = useOnboardingStore((s) => s.activating);
  const onboardingError = useOnboardingStore((s) => s.error);
  const updateDraft = useOnboardingStore((s) => s.updateDraft);
  const completeBirthTransition = useOnboardingStore((s) => s.completeBirthTransition);
  const reducedMotion = usePrefersReducedMotion();
  const modeMotion = useOnboardingModeMotion();
  const [recoveryDismissed, setRecoveryDismissed] = useState(false);
  const [retrying, setRetrying] = useState(false);
  const [controlBusy, setControlBusy] = useState(false);
  const [advancedOpen, setAdvancedOpen] = useState<BirthAdvancedSection | null>(null);
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
  const running = (uiPhase === "running" || isBirthEngineActive(status ?? { status: "idle" })) && !stageStalledActive;
  const genesisMode =
    birthSurface === "genesis" && !awakening && !recoveryOverlayActive && !failed;
  const checkpointAvailable = hasBirthCheckpointProgress(status?.progress);
  const { logs, connected } = usePPOEvolution(!failed && !awakening && !genesisMode);
  const recoveryKind = detectBirthRecoveryKind(status);
  const interrupted = status != null && isBirthInterrupted(status);
  const showRecovery =
    birthSurface === "recovery" &&
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

  const handleStopBirth = () => {
    setControlBusy(true);
    setAdvancedOpen(null);
    void useBirthStore
      .getState()
      .stopBirthRun()
      .then((ok) => {
        if (ok) {
          toast.success("Gestopt — kies Start birth of Wis birth-data voor schone run");
          return;
        }
        toast.error(useBirthStore.getState().pollError ?? "Stop failed");
      })
      .finally(() => setControlBusy(false));
  };

  const handleStartBirth = () => {
    setControlBusy(true);
    useBirthStore.getState().beginBirthRun();
    void activateBirth()
      .then(async (ok) => {
        if (ok) {
          await poll();
          return;
        }
        useBirthStore.getState().setBirthSurface("genesis");
        useBirthStore.setState({ uiPhase: "idle" });
        toast.error(onboardingError ?? "Birth start failed");
      })
      .finally(() => setControlBusy(false));
  };

  const handleWipeBirthData = () => {
    setControlBusy(true);
    void wipeAllBirthData()
      .then(() => poll())
      .then((status) => {
        useBirthStore.getState().reset();
        const payload = status ?? useBirthStore.getState().status;
        const topStatus = String(payload?.status ?? "").toLowerCase();
        const progress = payload?.progress;
        const hasCheckpoint =
          Number(progress?.cumulative_trades ?? progress?.trades_done ?? 0) > 0 ||
          Number(progress?.ppo_steps ?? progress?.ppo_steps_cumulative ?? 0) > 0;
        if ((topStatus !== "idle" && topStatus !== "wiped") || hasCheckpoint) {
          toast.error("Wipe voltooid maar status is niet schoon — herstart de backend en probeer opnieuw.");
          return;
        }
        toast.success("Alle birth-data gewist — klaar voor schone start");
      })
      .catch((e) => toast.error(e instanceof Error ? e.message : "Wipe failed"))
      .finally(() => setControlBusy(false));
  };

  const handleResumeCheckpoint = () => {
    setControlBusy(true);
    useBirthStore.getState().beginBirthRun();
    void startBirthSession({ targetTrades, continueTraining: true })
      .then(async () => {
        setBirthSurface("running");
        await poll();
        toast.success("Hervat vanaf checkpoint");
      })
      .catch((e) => toast.error(e instanceof Error ? e.message : "Resume failed"))
      .finally(() => setControlBusy(false));
  };

  const handleExtraTraining = () => {
    void clearBirthForExtraTraining()
      .then(() => startBirthSessionContinue(targetTrades))
      .then(() => {
        useBirthStore.setState({ uiPhase: "running", birthSurface: "running" });
        toast.success("Extra training started from checkpoint");
      })
      .catch((e) => toast.error(e instanceof Error ? e.message : "Extra training failed"));
  };

  const missionMode = birthSurface === "running" && (running || awakening);

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

  const handleCopyForensicsCommand = () => {
    void navigator.clipboard.writeText("python scripts/birth_stage_forensics.py");
    toast.success("Forensics command copied to clipboard");
  };

  const handleReviewGenesisSettings = () => {
    setRecoveryDismissed(true);
    useBirthStore.getState().setBirthSurface("genesis");
    setAdvancedOpen("settings");
    toast.info("Review genesis settings, save, then use Expand & retry.");
  };

  const stalledBlocker =
    String(status?.progress?.pass_reason ?? "").trim() ||
    String(status?.progress?.stage_blocker_metric ?? "").trim().replace(/_/g, " ");
  const adaptationTier = Math.max(0, Number(status?.progress?.adaptation_tier ?? 0) || 0);
  const maxAdaptationTiers = Math.max(1, Number(status?.progress?.max_adaptation_tiers ?? 4) || 4);
  const stalledRetries = Math.max(0, Number(status?.progress?.retries_this_stage ?? 0) || 0);
  const maxStageRetries = Math.max(1, Number(status?.progress?.max_stage_retries ?? 3) || 3);
  const stalledRetryable = status?.progress?.retryable !== false;
  const stalledAutoResume = stalledRetryable && shouldAutoResumeBirth(status);
  const tradeBudgetRemaining = Number(status?.progress?.trade_budget_remaining ?? NaN);
  const tradeBudgetCap = Number(status?.progress?.trade_budget_cap ?? status?.progress?.target_trades ?? 0);
  const terminalStallReason = String(status?.progress?.terminal_stall_reason ?? "").trim();
  const needsAttention = Boolean(status?.progress?.needs_attention);
  const attentionSummary = String(status?.progress?.attention_summary ?? "").trim();
  const constitutionSession = Number(status?.progress?.constitution_violations_session ?? NaN);
  const constitutionCumulative = Number(status?.progress?.constitution_violations_cumulative ?? NaN);

  const certificateFailureDetail =
    (Array.isArray(status?.failure_reasons) && status.failure_reasons.length > 0
      ? status.failure_reasons.join(" · ")
      : null) ||
    status?.message ||
    status?.certificate_reason ||
    "Review OOS metrics below and choose a recovery action.";

  return (
    <OnboardingShell className="birth-phase-screen birth-phase-screen--cinematic onboarding-shell--form">
      <motion.div
        className={cn(
          "birth-phase-cinematic relative mx-auto flex h-dvh min-h-0 w-full max-w-none flex-col overflow-hidden",
          recoveryOverlayActive && "birth-phase-cinematic--recovery-active",
        )}
        animate={{ opacity: transition.active ? 0.35 : 1 }}
        transition={transitionOrNone(reducedMotion, birthMotion)}
      >
        {genesisMode ? (
          <div className="relative flex min-h-0 flex-1 flex-col overflow-hidden">
            <BirthCommandBar
              mode="genesis"
              headline={
                activating
                  ? "Activation sequence engaged"
                  : interrupted
                    ? "Birth gestopt — kies volgende actie"
                    : "Neural Genesis — awaiting activation"
              }
              milestones={milestones}
              progress={status?.progress}
              status={status?.status ?? "idle"}
              checkpointAvailable={checkpointAvailable}
              busy={controlBusy || activating}
              onStart={handleStartBirth}
              onWipe={handleWipeBirthData}
              onResumeCheckpoint={handleResumeCheckpoint}
            />
            <div className="min-h-0 flex-1 overflow-hidden px-2 pb-4 md:px-6">
              <BirthCinematicLayout
                className="min-h-0 h-full"
                stage={
                  <div className="birth-activation-stage-inner birth-helix-accent-wrap pointer-events-none">
                    <div className="birth-activation-helix-slot birth-helix-accent">
                      <Suspense
                        fallback={
                          <div className="flex h-full min-h-0 flex-1 items-center justify-center">
                            <BirthOrganismVisual className="size-48 opacity-80" />
                          </div>
                        }
                      >
                        <BirthHelixVisual
                          ceremonyMode
                          activating={activating}
                          primed={activating}
                          trainingTrades={trainingDraft.training_trades}
                          className="h-full min-h-0 w-full max-w-md"
                        />
                      </Suspense>
                    </div>
                  </div>
                }
                deck={
                  <BirthGenesisDeck
                    training={trainingDraft}
                    activating={activating}
                    error={onboardingError}
                    onChangeTraining={(patch) => updateDraft({ training: { ...trainingDraft, ...patch } })}
                    onActivate={() => void handleStartBirth()}
                  />
                }
              />
            </div>
          </div>
        ) : missionMode ? (
          <div
            className={cn(
              "birth-mission-shell relative flex min-h-0 flex-1 flex-col overflow-hidden",
              awakening && "birth-finale-lock",
              recoveryOverlayActive && "invisible opacity-0",
            )}
          >
            <BirthCommandBar
              mode={awakening ? "finale" : "running"}
              headline={awakening ? "Birth complete" : headline}
              milestones={milestones}
              progress={status?.progress}
              status={status?.status ?? "idle"}
              busy={controlBusy}
              advancedOpen={advancedOpen}
              onToggleAdvanced={setAdvancedOpen}
              onStop={handleStopBirth}
              onEnterDeck={enterCommandDeck}
              onExtraTraining={handleExtraTraining}
            />
            <div className="birth-mission-grid min-h-0 flex-1 overflow-hidden p-3 md:p-4">
              <div className="birth-helix-accent-wrap pointer-events-none hidden min-h-0 lg:block">
                <Suspense
                  fallback={
                    <div className="flex h-full items-center justify-center">
                      <BirthOrganismVisual className="size-16 opacity-80" />
                    </div>
                  }
                >
                  <BirthHelixVisual
                    activating={helixActivating}
                    ceremonyMode
                    trainingTrades={targetTrades}
                    className="birth-helix-accent max-h-full w-full max-w-full"
                  />
                </Suspense>
              </div>
              <BirthMissionControl
                headline={awakening ? "Birth complete" : headline}
                subtitle={
                  awakening
                    ? "Your organism is trained and ready for the command deck."
                    : phaseSubtitle
                }
                milestones={milestones}
                progress={status?.progress}
                status={status}
                elapsedSeconds={status?.elapsed_seconds}
                progressMessage={status?.progress?.message ?? status?.message}
                finale={awakening}
                running={running}
                className="min-h-0"
              />
              <BirthStageIntelColumn
                progress={status?.progress}
                status={status}
                running={running}
                finale={awakening}
                advancedOpen={advancedOpen}
                onToggleAdvanced={setAdvancedOpen}
                settingsInitial={birthSettingsInitial}
                trainingLogs={logs}
                trainingConnected={connected}
                className="min-h-0"
              />
            </div>
          </div>
        ) : (
        <motion.div
          className="birth-phase-hero relative flex min-h-0 flex-1 flex-col overflow-hidden"
          animate={{ scale: 1 }}
          transition={transitionOrNone(reducedMotion, modeMotion)}
        >
          <div className="flex min-h-0 flex-1 items-center justify-center px-4">
            <p className="birth-phase-subtitle text-center text-sm">{phaseSubtitle}</p>
          </div>
        </motion.div>
        )}

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
              <>
                {stalledBlocker ? (
                  <p className="mt-2 rounded border border-amber-500/30 bg-amber-950/20 px-3 py-2 font-mono text-xs text-amber-100">
                    Blocker: {stalledBlocker}
                  </p>
                ) : null}
                {(terminalStallReason === "plateau_evolution_exhausted" ||
                  terminalStallReason === "stall_remediation_exhausted") ? (
                  <p className="mt-2 rounded border border-orange-500/30 bg-orange-950/20 px-3 py-2 font-mono text-xs text-orange-100">
                    Learning plateau: evolution and auto-remediation exhausted. Review genesis
                    settings (data window, reward), then Expand &amp; retry — wipe is unlikely to
                    help without config changes.
                  </p>
                ) : null}
                {needsAttention && attentionSummary ? (
                  <p className="mt-2 rounded border border-violet-500/30 bg-violet-950/20 px-3 py-2 font-mono text-xs text-violet-100">
                    {attentionSummary}
                  </p>
                ) : null}
                {terminalStallReason && terminalStallReason !== "plateau_evolution_exhausted" ? (
                  <p className="mt-2 font-mono text-[10px] text-muted-foreground">
                    Stall reason: {terminalStallReason}
                  </p>
                ) : null}
                {Number.isFinite(tradeBudgetRemaining) && tradeBudgetCap > 0 ? (
                  <p className="mt-2 font-mono text-[10px] text-muted-foreground">
                    Trade budget: {tradeBudgetRemaining.toLocaleString()} remaining of{" "}
                    {tradeBudgetCap.toLocaleString()}
                  </p>
                ) : null}
                {Number.isFinite(constitutionSession) && Number.isFinite(constitutionCumulative) ? (
                  <p className="mt-1 font-mono text-[10px] text-muted-foreground">
                    Constitution violations: {constitutionSession.toLocaleString()} this stage ·{" "}
                    {constitutionCumulative.toLocaleString()} cumulative
                  </p>
                ) : null}
                <p className="mt-2 text-xs text-muted-foreground">
                  {needsAttention
                    ? "Telegram alert sent — manual review required before retry."
                    : stalledAutoResume
                      ? "Auto-resume is active — the engine will retry automatically when the app or service restarts."
                      : stalledRetryable
                        ? "Manual action required — use Expand & retry or Review genesis settings below."
                        : "Recovery is not automatic for this stall state."}
                </p>
              </>
            }
            error={pollError}
                actions={
              <BirthRecoveryActionBar
                loading={retrying}
                actions={[
                  {
                    id: "expand",
                    label: "Expand & retry",
                    loadingLabel: "Starting…",
                    variant: "primary",
                    onClick: handleExpandAndRetryStalledStage,
                  },
                  {
                    id: "genesis",
                    label: "Review genesis settings",
                    variant: "secondary",
                    onClick: handleReviewGenesisSettings,
                  },
                  {
                    id: "retry",
                    label: "Retry stage",
                    variant: "secondary",
                    onClick: handleResumeStalledStage,
                  },
                  {
                    id: "forensics",
                    label: "Copy forensics cmd",
                    variant: "outline",
                    onClick: handleCopyForensicsCommand,
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
