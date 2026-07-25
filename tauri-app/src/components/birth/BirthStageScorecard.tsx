import type { BirthProgressPayload } from "@/lib/birthClient";
import {
  extractStageScorecard,
  shouldShowBirthAttentionBanner,
  type StageScorecardModel,
} from "@/lib/birthPhaseModel";
import { cn } from "@/lib/utils";

import { BirthFieldCard } from "@/components/birth/BirthFieldCard";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

interface BirthStageScorecardProps {
  progress: BirthProgressPayload | undefined;
  birthStatus?: string;
  birthRunning?: boolean;
  resumePlateauRisk?: boolean;
  resumePlateauRiskTrades?: number | null;
  variant?: "default" | "compact";
  className?: string;
}

function formatMetricValue(model: StageScorecardModel): string {
  if (model.metricValue == null) {
    if (model.passCriteriaId === "trend_winrate" && model.tradesDone > 0) {
      return "syncing…";
    }
    return "—";
  }
  if (model.passCriteriaId === "mixed_constitution") {
    return String(Math.round(model.metricValue));
  }
  return `${(model.metricValue * 100).toFixed(0)}%`;
}

function formatMetricTarget(model: StageScorecardModel): string {
  if (model.passCriteriaId === "mixed_constitution") {
    return "need 0";
  }
  if (model.passCriteriaId === "range_hold_ratio" || model.passCriteriaId === "range_roundtrip") {
    const min = model.metricMin != null ? (model.metricMin * 100).toFixed(0) : "30";
    const max = model.metricMax != null ? (model.metricMax * 100).toFixed(0) : "70";
    return `target ${min}–${max}%`;
  }
  if (model.metricTarget != null) {
    return `need ${(model.metricTarget * 100).toFixed(0)}%`;
  }
  return "";
}

function formatTrendSlope(slope: number | null): string {
  if (slope == null) return "—";
  if (Math.abs(slope) < 0.0001) return "flat";
  const pct = (slope * 100).toFixed(2);
  return slope > 0 ? `+${pct}%/step` : `${pct}%/step`;
}

function showAdaptationHud(scorecard: StageScorecardModel): boolean {
  return (
    scorecard.adaptationEnabled &&
    scorecard.wallBehavior === "adaptive" &&
    (scorecard.volumeGateStatus != null ||
      scorecard.retriesThisStage > 0 ||
      scorecard.lastAdaptationSummary != null)
  );
}

function formatDataWindow(scorecard: StageScorecardModel): string {
  if (scorecard.dataDaysLoaded == null || scorecard.dataDaysLoaded <= 0) return "—";
  if (
    scorecard.dataManifestDaysLoaded != null &&
    scorecard.dataManifestDaysLoaded > 0 &&
    scorecard.dataManifestDaysLoaded !== scorecard.dataDaysLoaded
  ) {
    return `${scorecard.dataManifestDaysLoaded}d cache → ${scorecard.dataDaysLoaded}d target`;
  }
  return `${scorecard.dataDaysLoaded}d loaded`;
}

function formatEvolutionAction(scorecard: StageScorecardModel): string {
  if (!scorecard.evolutionLastActionDetail) return "—";
  const prefix = scorecard.evolutionLastActionApplied
    ? "Applied"
    : scorecard.evolutionLastActionDetail.toLowerCase().includes("not stage1")
      ? "Skipped"
      : "Skipped";
  return `${prefix}: ${scorecard.evolutionLastActionDetail}`;
}

/** Pass-metric within gate and no active blocker → goal met (green). */
function isGoalMet(scorecard: StageScorecardModel): boolean {
  if (scorecard.blockerDetail) return false;
  if (scorecard.metricValue == null) return false;
  if (scorecard.passCriteriaId === "mixed_constitution") {
    return scorecard.metricValue <= 0;
  }
  if (
    scorecard.passCriteriaId === "range_hold_ratio" ||
    scorecard.passCriteriaId === "range_roundtrip"
  ) {
    const min = scorecard.metricMin ?? 0.3;
    const max = scorecard.metricMax ?? 0.7;
    return scorecard.metricValue >= min && scorecard.metricValue <= max;
  }
  if (scorecard.metricTarget != null) {
    return scorecard.metricValue >= scorecard.metricTarget;
  }
  return false;
}

function StageTabFields({ scorecard }: { scorecard: StageScorecardModel }) {
  const heartbeatLabel =
    scorecard.heartbeatSec != null
      ? `${scorecard.heartbeatSec}s ago`
      : "Awaiting update";
  const passMetricHint = formatMetricTarget(scorecard);
  const dataHint =
    scorecard.wallClockTradesPerMin != null
      ? `~${scorecard.wallClockTradesPerMin.toLocaleString()} trades/min · sim speed, not calendar`
      : "Sim runs at hardware speed, not calendar time";
  const goalMet = isGoalMet(scorecard);

  return (
    <div className="birth-intel-field-grid">
      <BirthFieldCard
        label="Goal"
        value={scorecard.goalLabel}
        hint={goalMet ? "Pass criteria met" : "Pass criteria not yet met"}
        tone={goalMet ? "ok" : "warn"}
        className="birth-intel-field-span"
      />
      {scorecard.blockerDetail ? (
        <BirthFieldCard
          label={scorecard.blockerLabel ?? "Blocking metric"}
          value={scorecard.blockerDetail}
          hint="Pass gate blocked"
          tone="danger"
          className="birth-intel-field-span"
        />
      ) : null}
      <BirthFieldCard
        label="Pass metric"
        value={formatMetricValue(scorecard)}
        hint={passMetricHint || undefined}
        tone={scorecard.blockerDetail ? "warn" : goalMet ? "ok" : "default"}
      />
      <BirthFieldCard
        label="Pass gate"
        value={
          scorecard.stagePassGateTrades != null
            ? scorecard.stagePassGateTrades.toLocaleString()
            : "—"
        }
        hint="Trades required to unlock pass evaluation"
      />
      <BirthFieldCard
        label="Budget"
        value={
          scorecard.stageBudgetTrades != null
            ? scorecard.stageBudgetTrades.toLocaleString()
            : "—"
        }
        hint={
          scorecard.plateauMinStageTrades != null
            ? `Plateau after ${scorecard.plateauMinStageTrades.toLocaleString()} trades`
            : undefined
        }
      />
      <BirthFieldCard
        label="Regime mix"
        value={scorecard.regimeDistributionSummary ?? "—"}
      />
      <BirthFieldCard
        label="Rolling WR (500)"
        value={
          scorecard.rollingWinrate500 != null && scorecard.tradesDone >= 50
            ? `${(scorecard.rollingWinrate500 * 100).toFixed(1)}%`
            : "—"
        }
      />
      <BirthFieldCard
        label="Data window"
        value={formatDataWindow(scorecard)}
        hint={dataHint}
      />
      <BirthFieldCard
        label="Sub-phase"
        value={scorecard.subPhaseLabel}
        hint={scorecard.explorationActive ? "Exploration active" : undefined}
      />
      <BirthFieldCard
        label="Heartbeat"
        value={heartbeatLabel}
        hint={scorecard.healthHint}
        tone={scorecard.health === "stale" ? "warn" : scorecard.health === "advancing" ? "ok" : "default"}
      />
      {scorecard.provisionalPass ? (
        <BirthFieldCard
          label="Pass mode"
          value="Provisional"
          hint="Practice only — not a certified pass"
          tone="warn"
          className="birth-intel-field-span"
        />
      ) : null}
    </div>
  );
}

function RecoveryTabFields({
  scorecard,
  resumePlateauRisk,
  resumePlateauRiskTrades,
}: {
  scorecard: StageScorecardModel;
  resumePlateauRisk: boolean;
  resumePlateauRiskTrades: number | null;
}) {
  const adapting = showAdaptationHud(scorecard);
  const stallActive =
    scorecard.stallRemediationCycle != null && scorecard.stallRemediationCycle > 0;

  return (
    <div className="space-y-2">
      {scorecard.adaptationCycling ? (
        <div className="risk-envelope-banner birth-distress-callout shrink-0 rounded px-2 py-1.5">
          <p className="birth-distress-callout__title tracking-wide">Recovery cycling</p>
          <p className="birth-distress-callout__body mt-0.5">
            Adaptation loop without train-laps. If trades stay frozen: rebuild + resume, or Reset
            birth (keep tick cache) as last resort.
          </p>
        </div>
      ) : null}
      {resumePlateauRisk ? (
        <div className="risk-envelope-banner birth-distress-callout shrink-0 rounded px-2 py-1.5">
          <p className="birth-distress-callout__title tracking-wide">Checkpoint resume risk</p>
          <p className="birth-distress-callout__body mt-0.5">
            Resume may re-trigger plateau
            {resumePlateauRiskTrades != null
              ? ` (${resumePlateauRiskTrades.toLocaleString()} stage trades loaded)`
              : ""}
            . Prefer Reset birth (keep tick cache) for a clean restart.
          </p>
        </div>
      ) : null}

      <div className="birth-intel-field-grid">
        <BirthFieldCard
          label="Volume gate"
          value={scorecard.volumeGateStatus ?? "—"}
          tone={
            scorecard.volumeGateStatus === "PASSED"
              ? "ok"
              : scorecard.volumeGateStatus === "PENDING"
                ? "warn"
                : "default"
          }
        />
        <BirthFieldCard
          label="Winrate trend"
          value={formatTrendSlope(scorecard.winrateTrendSlope)}
        />
        <BirthFieldCard
          label="Escalation tier"
          value={
            scorecard.adaptationTier != null && scorecard.maxAdaptationTiers != null
              ? `${scorecard.adaptationTier + 1}/${scorecard.maxAdaptationTiers}`
              : "—"
          }
        />
        <BirthFieldCard
          label="Exploration"
          value={
            scorecard.escalationLevel != null && scorecard.escalationLevel > 0
              ? `L${scorecard.escalationLevel}`
              : scorecard.explorationActive
                ? "active"
                : "—"
          }
        />
        <BirthFieldCard
          label="Auto-retries"
          value={
            scorecard.retriesThisStage > 0
              ? scorecard.maxStageRetries != null
                ? `${scorecard.retriesThisStage} / ${scorecard.maxStageRetries}`
                : String(scorecard.retriesThisStage)
              : adapting
                ? "0"
                : "—"
          }
        />
        <BirthFieldCard
          label="Autonomous recovery"
          value={
            scorecard.autonomousRecoveryRatePct != null &&
            scorecard.autonomousRecoveryRatePct > 0
              ? `${scorecard.autonomousRecoveryRatePct.toFixed(0)}%`
              : "—"
          }
          tone={scorecard.autoRecoveryActive ? "ok" : "default"}
          hint={scorecard.autoRecoveryActive ? "Auto-recovery active" : undefined}
        />
        <BirthFieldCard
          label="Last adaptation"
          value={scorecard.lastAdaptationSummary ?? "—"}
          className="birth-intel-field-span"
        />
        <BirthFieldCard
          label="Stall remediation"
          value={
            stallActive
              ? `Cycle ${scorecard.stallRemediationCycle}${
                  scorecard.stallRemediationMaxCycles != null
                    ? `/${scorecard.stallRemediationMaxCycles}`
                    : ""
                }${
                  scorecard.stallRemediationStep != null
                    ? ` · step ${scorecard.stallRemediationStep}${
                        scorecard.stallRemediationMaxSteps != null
                          ? `/${scorecard.stallRemediationMaxSteps}`
                          : ""
                      }`
                    : ""
                }`
              : "—"
          }
          tone={stallActive ? "warn" : "default"}
        />
        <BirthFieldCard
          label="Recommended action"
          value={
            scorecard.recommendedRecoveryAction
              ? scorecard.recommendedRecoveryAction.replace(/_/g, " ")
              : "—"
          }
        />
        {scorecard.passCriteriaId === "trend_winrate" &&
        scorecard.stage1WinrateGate != null &&
        scorecard.stage1WinrateRecommended != null &&
        scorecard.stage1WinrateGate < scorecard.stage1WinrateRecommended - 0.001 ? (
          <BirthFieldCard
            label="Winrate gate"
            value={`${(scorecard.stage1WinrateGate * 100).toFixed(0)}%`}
            hint={`Recommended ${(scorecard.stage1WinrateRecommended * 100).toFixed(0)}% · REAL needs Evolution Proof + OOS ≥48%`}
            tone="warn"
            className="birth-intel-field-span"
          />
        ) : null}
      </div>
    </div>
  );
}

function EvolutionTabFields({ scorecard }: { scorecard: StageScorecardModel }) {
  const evolutionActive =
    scorecard.evolutionPhase != null && scorecard.evolutionPhase !== "none";
  const stepLabel =
    scorecard.evolutionStepLabel ??
    (scorecard.evolutionPhase
      ? `Evolution ${scorecard.evolutionPhase.replace(/_/g, " ")}`
      : "—");

  let actionsDetail = "—";
  if (
    scorecard.evolutionActionsTotal != null &&
    scorecard.evolutionActionsCompleted != null
  ) {
    actionsDetail = `${scorecard.evolutionActionsCompleted}/${scorecard.evolutionActionsTotal}`;
  } else if (
    scorecard.evolutionStep != null &&
    scorecard.evolutionActionsRemaining != null
  ) {
    actionsDetail = `step ${scorecard.evolutionStep}/${scorecard.evolutionStep + scorecard.evolutionActionsRemaining}`;
  }

  return (
    <div className="birth-intel-field-grid">
      <BirthFieldCard
        label="Evolution phase"
        value={evolutionActive ? stepLabel : "—"}
        hint={
          scorecard.evolutionPhantomSteps != null && scorecard.evolutionPhantomSteps > 0
            ? `Phantom steps: ${scorecard.evolutionPhantomSteps}`
            : undefined
        }
        tone={evolutionActive ? "warn" : "default"}
      />
      <BirthFieldCard label="Actions" value={actionsDetail} />
      <BirthFieldCard
        label="Rollouts this step"
        value={
          scorecard.evolutionRolloutsThisStep != null &&
          scorecard.evolutionRolloutsMax != null
            ? `${scorecard.evolutionRolloutsThisStep}/${scorecard.evolutionRolloutsMax}`
            : "—"
        }
      />
      <BirthFieldCard
        label="Plateau clock"
        value={
          scorecard.plateauElapsedSec != null
            ? `${Math.ceil(scorecard.plateauElapsedSec / 60)}m elapsed`
            : "—"
        }
      />
      <BirthFieldCard
        label="Trades beyond gate"
        value={
          scorecard.tradesBeyondGate != null
            ? scorecard.tradesBeyondGate.toLocaleString()
            : "—"
        }
      />
      <BirthFieldCard
        label="Hold trap"
        value={scorecard.holdTrapDetected ? "Active" : "—"}
        tone={scorecard.holdTrapDetected ? "warn" : "default"}
      />
      <BirthFieldCard
        label="Last evolution action"
        value={formatEvolutionAction(scorecard)}
        className="birth-intel-field-span"
      />
      <BirthFieldCard
        label="Plateau quarantine"
        value={
          scorecard.plateauQuarantineActive
            ? "Resume grace — detection paused"
            : "—"
        }
        hint={
          scorecard.plateauQuarantineActive
            ? [
                scorecard.plateauQuarantineRolloutsRemaining != null
                  ? `${scorecard.plateauQuarantineRolloutsRemaining} rollouts`
                  : null,
                scorecard.plateauQuarantineTradesRemainingCount != null &&
                scorecard.plateauQuarantineTradesRemainingCount > 0
                  ? `${scorecard.plateauQuarantineTradesRemainingCount} trades remaining`
                  : scorecard.plateauQuarantineTradesRemaining != null
                    ? `${scorecard.plateauQuarantineTradesRemaining} new trades`
                    : null,
              ]
                .filter(Boolean)
                .join(" · ") || undefined
            : undefined
        }
        tone={scorecard.plateauQuarantineActive ? "accent" : "default"}
        className="birth-intel-field-span"
      />
    </div>
  );
}

export function BirthStageScorecard({
  progress,
  birthStatus,
  birthRunning = false,
  resumePlateauRisk = false,
  resumePlateauRiskTrades = null,
  variant = "default",
  className,
}: BirthStageScorecardProps) {
  const scorecard = extractStageScorecard(progress);
  if (!scorecard) return null;

  const compact = variant === "compact";

  if (compact) {
    return (
      <p
        className={cn(
          "birth-stage-scorecard-compact font-mono text-[11px] text-cyan-200/85",
          className,
        )}
      >
        {scorecard.stageLabel} · {scorecard.tradesDone}/{scorecard.tradesRequired} trades
        {scorecard.metricValue != null
          ? ` · ${scorecard.metricLabel} ${formatMetricValue(scorecard)}`
          : ""}
        {scorecard.learningAttempt > 0 ? ` · attempt ${scorecard.learningAttempt}` : ""}
        {scorecard.patternsMined > 0
          ? ` · ${scorecard.patternsMined.toLocaleString()} patterns`
          : ""}
        {scorecard.explorationActive ? " · explore" : ""}
        {scorecard.stageWallRemainingSec != null
          ? ` · wall ${Math.ceil(scorecard.stageWallRemainingSec / 60)}m`
          : ""}
        {showAdaptationHud(scorecard) && scorecard.volumeGateStatus
          ? ` · gate ${scorecard.volumeGateStatus}`
          : ""}
        {scorecard.retriesThisStage > 0 ? ` · adapt ${scorecard.retriesThisStage}` : ""}
      </p>
    );
  }

  const attention = shouldShowBirthAttentionBanner(progress, {
    birthRunning,
    birthStatus,
  });
  const defaultTab =
    scorecard.adaptationCycling ||
    (scorecard.stallRemediationCycle != null && scorecard.stallRemediationCycle > 0)
      ? "recovery"
      : scorecard.evolutionPhase && scorecard.evolutionPhase !== "none"
        ? "evolution"
        : "stage";

  return (
    <div className={cn("birth-stage-scorecard flex min-h-0 flex-1 flex-col", className)}>
      {attention ? (
        <div className="risk-envelope-banner risk-envelope-banner--info mx-0 mb-2 shrink-0">
          <p className="text-[11px] leading-relaxed">
            <strong className="text-violet-200/90">Attention required:</strong>{" "}
            {String(progress?.attention_summary ?? "Lumina needs operator review.")}
          </p>
        </div>
      ) : null}

      <Tabs defaultValue={defaultTab} className="risk-envelope-tabs birth-stage-scorecard__tabs min-h-0 flex-1">
        <TabsList className="risk-envelope-tab-list risk-envelope-tab-list--3 w-full shrink-0">
          <TabsTrigger value="stage">Stage</TabsTrigger>
          <TabsTrigger value="recovery">Recovery</TabsTrigger>
          <TabsTrigger value="evolution">Evolution</TabsTrigger>
        </TabsList>

        <div className="risk-envelope-tab-body birth-stage-scorecard__tab-body min-h-0 flex-1 overflow-x-hidden overflow-y-auto">
          <TabsContent value="stage" className="risk-envelope-tab-content mt-0">
            <StageTabFields scorecard={scorecard} />
          </TabsContent>
          <TabsContent value="recovery" className="risk-envelope-tab-content mt-0">
            <RecoveryTabFields
              scorecard={scorecard}
              resumePlateauRisk={resumePlateauRisk}
              resumePlateauRiskTrades={resumePlateauRiskTrades}
            />
          </TabsContent>
          <TabsContent value="evolution" className="risk-envelope-tab-content mt-0">
            <EvolutionTabFields scorecard={scorecard} />
          </TabsContent>
        </div>
      </Tabs>
    </div>
  );
}
