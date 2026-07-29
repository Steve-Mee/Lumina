import { BirthCompletionSummary } from "@/components/birth/BirthCompletionSummary";
import { BirthFailureOverlayShell } from "@/components/birth/BirthFailureOverlayShell";
import { BirthRecoveryActionBar } from "@/components/birth/BirthRecoveryActionBar";
import { BirthRecoveryPanel } from "@/components/birth/BirthRecoveryPanel";
import { BirthRemediationBar } from "@/components/birth/BirthRemediationBar";
import { BirthStageScorecard } from "@/components/birth/BirthStageScorecard";
import { Button } from "@/components/ui/button";
import type { BirthPhaseActions } from "@/hooks/useBirthPhaseActions";
import type { BirthPhaseDerived } from "@/hooks/useBirthPhaseDerived";
import { isTransientPollWarning } from "@/store/birthStore";
import {
  distressPanelClass,
  warnOverlayBodyClass,
  warnOverlayPanelClass,
  warnOverlayTitleClass,
} from "@/lib/modePresentation";
import { cn } from "@/lib/utils";

interface BirthPhaseRecoveryOverlaysProps {
  derived: BirthPhaseDerived;
  retrying: boolean;
  certificateFailureDetail: string;
  stalledRecoveryActions: BirthPhaseActions["stalledRecoveryActions"];
  onDismissRecovery: () => void;
  onResumeBirth: () => void;
  onReuseDataBirth: () => void;
  onWipeRetryBirth: () => void;
  onReturnToGenesis: () => void;
  onRetryBirth: () => void;
}

export function BirthPhaseRecoveryOverlays({
  derived,
  retrying,
  certificateFailureDetail,
  stalledRecoveryActions,
  onDismissRecovery,
  onResumeBirth,
  onReuseDataBirth,
  onWipeRetryBirth,
  onReturnToGenesis,
  onRetryBirth,
}: BirthPhaseRecoveryOverlaysProps) {
  const {
    showRecovery,
    genesisMode,
    status,
    targetTrades,
    certificateFailed,
    stageStalledActive,
    phaseSubtitle,
    stalledBlocker,
    terminalStallReason,
    needsAttention,
    attentionSummary,
    provisionalGraduation,
    stallDiagnostics,
    tradeBudgetRemaining,
    tradeBudgetCap,
    constitutionSession,
    constitutionCumulative,
    autonomousMode,
    stalledAutoResume,
    stalledRetryable,
    pollError,
    running,
    resumePlateauRisk,
    adaptationTier,
    maxAdaptationTiers,
    stalledRetries,
    maxStageRetries,
    uiPhase,
    failed,
  } = derived;

  return (
    <>
      {/* Genesis Recovery tab owns resume/wipe UI — avoid a second messy action strip. */}
      {showRecovery && !genesisMode ? (
        <BirthRecoveryPanel
          status={status}
          targetTrades={targetTrades}
          className="relative z-30 mx-4 mb-2 shrink-0"
          onDismiss={onDismissRecovery}
        />
      ) : null}

      {certificateFailed ? (
        <BirthFailureOverlayShell
          className="birth-phase-certificate-overlay z-40"
          title="Certificate not passed"
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
                  onClick: onResumeBirth,
                },
                {
                  id: "reuse",
                  label: "Reuse data & retry",
                  variant: "secondary",
                  onClick: onReuseDataBirth,
                },
                {
                  id: "wipe",
                  label: "Wipe & restart",
                  variant: "outline",
                  onClick: onWipeRetryBirth,
                },
                {
                  id: "setup",
                  label: "Return to Genesis",
                  variant: "ghost",
                  onClick: onReturnToGenesis,
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
                <p className="birth-distress-callout birth-distress-callout__body mt-2 rounded px-3 py-2 text-xs">
                  Blocker: {stalledBlocker}
                </p>
              ) : null}
              {terminalStallReason === "plateau_evolution_exhausted" ||
              terminalStallReason === "stall_remediation_exhausted" ? (
                <p className="mt-2 rounded border border-orange-500/30 bg-orange-950/20 px-3 py-2 font-mono text-xs text-orange-100">
                  Learning plateau: evolution and auto-remediation exhausted. Use Wis
                  birth-data (tick cache may be kept) for a clean restart via Genesis — checkpoint
                  resume will re-trigger plateau without quarantine.
                </p>
              ) : null}
              {needsAttention && attentionSummary ? (
                <p className="mt-2 rounded border border-violet-500/30 bg-violet-950/20 px-3 py-2 font-mono text-xs text-violet-100">
                  {attentionSummary}
                </p>
              ) : null}
              {provisionalGraduation ? (
                <p className="birth-info-callout birth-info-callout__text mt-2 rounded px-3 py-2 text-xs">
                  Provisional graduation recorded — partial DNA seeded for Evolution. Retry or
                  continue via Expand &amp; retry.
                </p>
              ) : null}
              {terminalStallReason && terminalStallReason !== "plateau_evolution_exhausted" ? (
                <p className="mt-2 font-mono text-[10px] text-muted-foreground">
                  Stall reason: {terminalStallReason}
                </p>
              ) : null}
              {stallDiagnostics != null ? (
                <pre className="mt-2 max-h-32 overflow-auto rounded border border-border/40 bg-black/30 p-2 font-mono text-[10px] text-muted-foreground">
                  {typeof stallDiagnostics === "string"
                    ? stallDiagnostics
                    : JSON.stringify(stallDiagnostics, null, 2)}
                </pre>
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
                {autonomousMode
                  ? "Organism autonomy active — recovery runs without operator input."
                  : needsAttention
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
            autonomousMode ? (
              <p className="birth-info-callout__subtle text-center">
                Telemetry only — autonomous recovery in progress
              </p>
            ) : (
              <BirthRecoveryActionBar loading={retrying} actions={stalledRecoveryActions} />
            )
          }
        >
          <BirthStageScorecard
            progress={status?.progress}
            birthRunning={running}
            birthStatus={status?.status}
            resumePlateauRisk={resumePlateauRisk}
            resumePlateauRiskTrades={status?.resume_plateau_risk_trades ?? null}
          />
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
            <Button type="button" className="onboarding-cta" onClick={onRetryBirth}>
              Retry birth
            </Button>
            <Button
              type="button"
              variant="ghost"
              className="text-muted-foreground"
              onClick={onReturnToGenesis}
            >
              Return to Genesis
            </Button>
          </div>
        </div>
      ) : null}

      {pollError && !failed ? (
        <p
          className={cn(
            "relative z-30 mx-auto mb-3 max-w-md shrink-0 px-4 text-center text-xs",
            isTransientPollWarning(pollError)
              ? "text-muted-foreground"
              : distressPanelClass("warn"),
          )}
        >
          {pollError}
        </p>
      ) : null}
    </>
  );
}
