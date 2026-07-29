import type { BirthProgressPayload } from "@/lib/birthClient";
import {
  formatBirthEdgeScorePercent,
  formatBirthExpectancyPercent,
  formatBirthMetricTarget,
  formatBirthMetricValue,
} from "@/lib/birth/birthMetricFormat";
import {
  extractStageScorecard,
  shouldShowBirthAttentionBanner,
  type StageScorecardModel,
} from "@/lib/birthPhaseModel";
import { isStageGoalMet } from "@/lib/birth/birthStageScorecard";
import { cn } from "@/lib/utils";
import { useBirthStore } from "@/store/birthStore";

import { BirthFieldCard } from "@/components/birth/BirthFieldCard";
import { Button } from "@/components/ui/button";
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
  return formatBirthMetricValue(model);
}

function formatMetricTarget(model: StageScorecardModel): string {
  return formatBirthMetricTarget(model);
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
    return `${scorecard.dataManifestDaysLoaded}d cache -> ${scorecard.dataDaysLoaded}d target`;
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

/** Pass criteria met: EdgeScore uses composite blockers, not hygiene target. */
function isGoalMet(scorecard: StageScorecardModel): boolean {
  return isStageGoalMet(scorecard);
}

/** Single-instrument Hygiene WR readout (lifetime + rolling in hint — no triple cards). */
function formatHygieneInstrumentValue(scorecard: StageScorecardModel): string {
  if (scorecard.hygieneWrEffective != null) {
    return `${(scorecard.hygieneWrEffective * 100).toFixed(1)}%`;
  }
  if (scorecard.hygieneWrLifetime != null) {
    return `${(scorecard.hygieneWrLifetime * 100).toFixed(1)}%`;
  }
  return "—";
}

function formatHygieneInstrumentHint(scorecard: StageScorecardModel): string {
  const floor =
    scorecard.hygieneWrFloor != null
      ? `≥${(scorecard.hygieneWrFloor * 100).toFixed(0)}%`
      : "≥35%";
  const life =
    scorecard.hygieneWrLifetime != null
      ? `${(scorecard.hygieneWrLifetime * 100).toFixed(1)}%`
      : "—";
  const roll =
    scorecard.hygieneWrRolling != null || scorecard.rollingWinrate500 != null
      ? `${(((scorecard.hygieneWrRolling ?? scorecard.rollingWinrate500) as number) * 100).toFixed(1)}%`
      : null;
  const covered = scorecard.rollingWindowTradesCovered;
  const rollNote =
    roll == null
      ? null
      : scorecard.rollingWrEligible === false
        ? `roll ${roll} (${covered ?? 0}/400)`
        : scorecard.rollingWrEligible === true
          ? `roll ${roll} eligible`
          : `roll ${roll}`;
  const source = scorecard.hygieneWrSource ? ` · ${scorecard.hygieneWrSource}` : "";
  return [`life ${life}`, rollNote, `need ${floor}${source}`].filter(Boolean).join(" · ");
}

function StageTabFields({
  scorecard,
  progress,
}: {
  scorecard: StageScorecardModel;
  progress?: BirthProgressPayload;
}) {
  const heartbeatLabel =
    scorecard.heartbeatSec != null
      ? `${scorecard.heartbeatSec}s ago`
      : "Awaiting update";
  const passMetricHint = formatMetricTarget(scorecard);
  const dataHint =
    scorecard.wallClockTradesPerMin != null
      ? `~${scorecard.wallClockTradesPerMin.toLocaleString()} trades/min | sim speed, not calendar`
      : "Sim runs at hardware speed, not calendar time";
  const goalMet = isGoalMet(scorecard);
  const entropyAlive = progress?.entropy_alive;
  const policyEntropy = progress?.policy_entropy;
  const entropyMissing =
    entropyAlive === false && (policyEntropy == null || !Number.isFinite(policyEntropy));
  // missing = telemetry dark; dead = measured below floor (Starship honesty).
  const entropyValue =
    entropyMissing
      ? "missing"
      : entropyAlive === false
        ? "dead"
        : entropyAlive === true
          ? "alive"
          : "—";
  const entropyHint =
    policyEntropy != null && Number.isFinite(policyEntropy)
      ? `H=${Number(policyEntropy).toFixed(3)}`
      : entropyMissing
        ? "awaiting PPO entropy sample"
        : progress?.starship_exploration_burst_active
          ? "exploration burst active"
          : undefined;
  const entropyTone =
    entropyMissing ? "warn" : entropyAlive === false ? "danger" : entropyAlive === true ? "ok" : "default";
  const bestEdge = formatBirthEdgeScorePercent(progress?.best_edgescore);
  const swarmReject = Boolean(progress?.swarm_rejected_no_lift);
  const expectancy = formatBirthExpectancyPercent(progress?.expectancy_proxy);
  const expectancyTone =
    expectancy.value !== "—"
      ? Number(progress?.expectancy_proxy) >= -0.15
        ? "ok"
        : "warn"
      : "default";

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
        label="EdgeScore"
        value={formatMetricValue(scorecard)}
        hint={passMetricHint || undefined}
        tone={scorecard.blockerDetail ? "warn" : goalMet ? "ok" : "default"}
      />
      <BirthFieldCard
        label="Entropy"
        value={entropyValue}
        hint={entropyHint}
        tone={entropyTone}
      />
      <BirthFieldCard
        label="Expectancy"
        value={expectancy.value}
        hint={expectancy.hint}
        tone={expectancyTone}
      />
      <BirthFieldCard
        label="Champion EdgeScore"
        value={bestEdge}
        hint={swarmReject ? "frozen after swarm no-lift" : "best EdgeScore this stage"}
        tone={swarmReject ? "warn" : "default"}
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
        value={scorecard.regimeDistributionSummary?.trim() || "No regime mix yet"}
      />
      <BirthFieldCard
        label="Hygiene WR"
        value={formatHygieneInstrumentValue(scorecard)}
        hint={formatHygieneInstrumentHint(scorecard)}
        tip="Pass hygiene: lifetime OR trusted rolling (≥400 covered) ≥ floor. Rolling is an alternate evidence path, not a vanity metric."
        tone={
          scorecard.hygieneWrEffective != null &&
          scorecard.hygieneWrFloor != null &&
          scorecard.hygieneWrEffective >= scorecard.hygieneWrFloor
            ? "ok"
            : scorecard.blockerDetail?.toLowerCase().includes("hygiene")
              ? "warn"
              : "default"
        }
        className="birth-intel-field-span"
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
                    ? ` | step ${scorecard.stallRemediationStep}${
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
            hint={`Recommended ${(scorecard.stage1WinrateRecommended * 100).toFixed(0)}% | REAL needs Evolution Proof + OOS >=48%`}
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
                .join(" | ") || undefined
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
        {scorecard.stageLabel} | {scorecard.tradesDone}/{scorecard.tradesRequired} trades
        {scorecard.metricValue != null
          ? ` | ${scorecard.metricLabel} ${formatMetricValue(scorecard)}`
          : ""}
        {scorecard.learningAttempt > 0 ? ` | attempt ${scorecard.learningAttempt}` : ""}
        {scorecard.patternsMined > 0
          ? ` | ${scorecard.patternsMined.toLocaleString()} patterns`
          : ""}
        {scorecard.explorationActive ? " | explore" : ""}
        {scorecard.stageWallRemainingSec != null
          ? ` | wall ${Math.ceil(scorecard.stageWallRemainingSec / 60)}m`
          : ""}
        {showAdaptationHud(scorecard) && scorecard.volumeGateStatus
          ? ` | gate ${scorecard.volumeGateStatus}`
          : ""}
        {scorecard.retriesThisStage > 0 ? ` | adapt ${scorecard.retriesThisStage}` : ""}
      </p>
    );
  }

  const attention = shouldShowBirthAttentionBanner(progress, {
    birthRunning,
    birthStatus,
  });
  const acceptChampion = useBirthStore((s) => s.acceptChampion);
  const wipeBirthData = useBirthStore((s) => s.wipeBirthData);
  const actions = Array.isArray(progress?.attention_recommended_actions)
    ? progress.attention_recommended_actions.map((a) => String(a))
    : [];
  const showAccept = actions.includes("accept_champion") || actions.includes("resume_champion");
  const showWipe = actions.includes("wipe_and_retry");
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
        <div className="risk-envelope-banner risk-envelope-banner--info mx-0 mb-2 shrink-0 space-y-2">
          <p className="text-[11px] leading-relaxed">
            <strong className="text-violet-200/90">Attention required:</strong>{" "}
            {String(progress?.attention_summary ?? "Lumina needs operator review.")}
          </p>
          {showAccept || showWipe ? (
            <div className="flex flex-wrap gap-2">
              {showAccept ? (
                <Button
                  type="button"
                  size="sm"
                  variant="secondary"
                  className="h-7 text-[11px]"
                  onClick={() => void acceptChampion()}
                >
                  Accept champion
                </Button>
              ) : null}
              {showWipe ? (
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  className="h-7 text-[11px]"
                  onClick={() => void wipeBirthData({ preserveTickCache: true })}
                >
                  Wipe &amp; retry
                </Button>
              ) : null}
            </div>
          ) : null}
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
            <StageTabFields scorecard={scorecard} progress={progress} />
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
