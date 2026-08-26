import { usePPOEvolution } from "@/hooks/usePPOEvolution";
import {
  detectBirthRecoveryKind,
  isBirthCheckpointResumable,
  shouldAutoResumeBirth,
} from "@/lib/birthRecoveryModel";
import {
  isBirthCertificateFailed,
  isBirthEngineActive,
  isBirthEngineLive,
  isBirthInterrupted,
  resolveBirthPhaseCopy,
} from "@/lib/birthPhaseModel";
import type { BirthSettingsPayload } from "@/lib/birthClient";
import { resolveGenesisDeckPresentation } from "@/lib/birthGenesisPresentation";
import { resolveBirthOperatorMode } from "@/lib/birthOperatorMode";
import { resolveBirthScreenPhaseHeader } from "@/lib/luminaPhasePresentation";
import { useBirthStore } from "@/store/birthStore";
import { useBirthUiStore } from "@/store/birthUiStore";
import { useOnboardingStore } from "@/store/onboardingStore";

export function useBirthPhaseDerived(recoveryDismissed: boolean) {
  const headline = useBirthStore((s) => s.headline);
  const milestones = useBirthStore((s) => s.milestones);
  const status = useBirthStore((s) => s.status);
  const uiPhase = useBirthStore((s) => s.uiPhase);
  const birthSurface = useBirthStore((s) => s.birthSurface);
  const pollError = useBirthStore((s) => s.pollError);
  const sessionHydrated = useBirthStore((s) => s.sessionHydrated);
  const sessionProbeState = useBirthStore((s) => s.sessionProbeState);
  const targetTrades = useBirthStore((s) => s.targetTrades);
  const genesisPinned = useBirthStore((s) => s.genesisPinned);
  const runPinned = useBirthStore((s) => s.runPinned);
  const autonomousMode = useBirthUiStore((s) => s.autonomousMode);
  const activating = useOnboardingStore((s) => s.activating);
  const activationStep = useOnboardingStore((s) => s.activationStep);
  const onboardingError = useOnboardingStore((s) => s.error);
  const trainingDraft = useOnboardingStore((s) => s.draft.training);

  const operatorMode = resolveBirthOperatorMode({
    status,
    activating,
    runPinned,
    genesisPinned,
    uiPhase,
    recoveryDismissed,
  });

  const awakening = operatorMode === "finale" || uiPhase === "finale";
  const certificateFailed = operatorMode === "certificate_overlay";
  const stageStalledActive = operatorMode === "stall_overlay";
  const recoveryOverlayActive = certificateFailed || stageStalledActive;
  // Never treat decision/genesis as failed orphan; cert overlay still counts as failed.
  const failed = certificateFailed;
  const running =
    (operatorMode === "training" ||
      operatorMode === "launching" ||
      uiPhase === "running" ||
      isBirthEngineActive(status ?? { status: "idle" })) &&
    !stageStalledActive;
  const engineActive =
    status != null &&
    !genesisPinned &&
    (status.live === true || isBirthEngineActive(status));
  const genesisMode =
    (operatorMode === "idle" || operatorMode === "decision") &&
    !awakening &&
    !recoveryOverlayActive &&
    !engineActive;
  const launchingMode = operatorMode === "launching";
  const decisionMode = operatorMode === "decision";
  const engineLive = (genesisMode || engineActive) && status != null && isBirthEngineLive(status);
  const checkpointAvailable = isBirthCheckpointResumable(status);
  const { logs, connected } = usePPOEvolution(
    !awakening && !genesisMode && !launchingMode && operatorMode === "training",
  );
  const recoveryKind = detectBirthRecoveryKind(status);
  const interrupted = status != null && isBirthInterrupted(status);
  const certificateFailedPinned =
    genesisPinned && status != null && isBirthCertificateFailed(status);
  // Legacy recovery panel only for non-genesis recovery surface (stall/cert use overlays).
  const showRecovery =
    decisionMode &&
    birthSurface === "recovery" &&
    (Boolean(recoveryKind) || interrupted) &&
    !recoveryDismissed &&
    !certificateFailed &&
    !stageStalledActive &&
    !awakening &&
    !activating;

  const birthSettingsInitial: Partial<BirthSettingsPayload> = {
    training_trades: targetTrades,
    prefer_real_data_only: trainingDraft.prefer_real_data_only,
    max_real_days: trainingDraft.max_real_days,
    allow_minimal_synthetic_fallback: trainingDraft.allow_minimal_synthetic_fallback,
    require_real_simulator_data: trainingDraft.require_real_simulator_data,
    stage1_winrate_pass_threshold:
      status?.progress?.stage1_winrate_gate != null
        ? Number(status.progress.stage1_winrate_gate)
        : 0.45,
  };

  const helixActivating = running || awakening;
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

  // Full vault mission chrome whenever the engine is live or we are in running/finale —
  // never drop to a subtitle-only hero mid-birth (regime map / policy init included).
  const missionMode =
    operatorMode === "training" ||
    operatorMode === "finale" ||
    ((birthSurface === "running" || engineActive) && (running || awakening || engineActive));

  // Align phase header with Genesis deck SSOT (one narrative, no dual idle/stopped copy).
  const genesisPresentation = resolveGenesisDeckPresentation({
    activating,
    sessionInterrupted: interrupted,
    checkpointAvailable,
    resumePlateauRisk: Boolean(status?.resume_plateau_risk),
    decisionMode,
    sessionProbePending: sessionProbeState === "pending" || !sessionHydrated,
    sessionProbeError: sessionProbeState === "error",
    engineLive,
    error: onboardingError,
    pollError,
    statusMessage: status?.message ?? status?.progress?.message ?? null,
    statusError: status?.error ?? null,
  });
  // Align header with deck SSOT — clean idle after wipe is not "needs attention".
  const genesisAttention =
    genesisMode &&
    (genesisPresentation.hasAttention ||
      genesisPresentation.ctaMode === "retry" ||
      genesisPresentation.ctaMode === "decision");

  const phaseHeader = resolveBirthScreenPhaseHeader({
    genesisMode,
    missionMode,
    awakening,
    activating,
    launching: launchingMode,
    decisionMode,
    genesisAttention,
    genesisPhaseStatus: genesisMode ? genesisPresentation.phaseStatus : undefined,
    genesisPhaseTone: genesisMode ? genesisPresentation.phaseTone : undefined,
    interrupted,
    certificateFailed,
    certificateOverlayActive: certificateFailed,
    stageStalledActive,
    milestones,
    phaseSubtitle,
  });

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
  const tradeBudgetCap = Number(
    status?.progress?.trade_budget_cap ?? status?.progress?.target_trades ?? 0,
  );
  const terminalStallReason = String(status?.progress?.terminal_stall_reason ?? "").trim();
  const stallDiagnostics = status?.progress?.stall_diagnostics;
  const provisionalGraduation = Boolean(status?.progress?.provisional_graduation);
  const evolutionExhausted =
    terminalStallReason === "plateau_evolution_exhausted" ||
    terminalStallReason === "stall_remediation_exhausted";
  const resumePlateauRisk = Boolean(status?.resume_plateau_risk);
  const needsAttention = Boolean(status?.progress?.needs_attention);
  const attentionSummary = String(status?.progress?.attention_summary ?? "").trim();
  const constitutionSession = Number(status?.progress?.constitution_violations_session ?? NaN);
  const constitutionCumulative = Number(
    status?.progress?.constitution_violations_cumulative ?? NaN,
  );

  return {
    headline,
    milestones,
    status,
    uiPhase,
    pollError,
    sessionHydrated,
    sessionProbeState,
    /** True until first status arrives — Activate must stay locked. */
    sessionProbePending: sessionProbeState === "pending" || !sessionHydrated,
    targetTrades,
    genesisPinned,
    autonomousMode,
    activating,
    activationStep,
    operatorMode,
    launchingMode,
    decisionMode,
    genesisAttention,
    genesisPresentation,
    onboardingError,
    trainingDraft,
    awakening,
    certificateFailed,
    stageStalledActive,
    recoveryOverlayActive,
    failed,
    running,
    engineActive,
    genesisMode,
    engineLive,
    checkpointAvailable,
    logs,
    connected,
    recoveryKind,
    interrupted,
    certificateFailedPinned,
    showRecovery,
    birthSettingsInitial,
    helixActivating,
    phaseSubtitle,
    missionMode,
    phaseHeader,
    stalledBlocker,
    adaptationTier,
    maxAdaptationTiers,
    stalledRetries,
    maxStageRetries,
    stalledRetryable,
    stalledAutoResume,
    tradeBudgetRemaining,
    tradeBudgetCap,
    terminalStallReason,
    stallDiagnostics,
    provisionalGraduation,
    evolutionExhausted,
    resumePlateauRisk,
    needsAttention,
    attentionSummary,
    constitutionSession,
    constitutionCumulative,
  };
}

export type BirthPhaseDerived = ReturnType<typeof useBirthPhaseDerived>;
