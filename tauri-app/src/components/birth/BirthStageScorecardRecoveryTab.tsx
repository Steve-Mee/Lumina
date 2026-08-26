/** Recovery tab fields for BirthStageScorecard. */
import type { StageScorecardModel } from "@/lib/birthPhaseModel";
import { BirthFieldCard } from "@/components/birth/BirthFieldCard";
import {
  formatTrendSlope,
  showAdaptationHud,
} from "@/components/birth/BirthStageScorecardFormat";

export function RecoveryTabFields({
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
          tone={
            scorecard.winrateTrendSlope == null
              ? "default"
              : scorecard.winrateTrendSlope > 0.00005
                ? "ok"
                : scorecard.winrateTrendSlope < -0.00005
                  ? "danger"
                  : "warn"
          }
          hint={
            scorecard.winrateTrendSlope == null
              ? undefined
              : scorecard.winrateTrendSlope > 0
                ? "Improving — good direction"
                : scorecard.winrateTrendSlope < 0
                  ? "Declining — wrong direction"
                  : "Flat trend"
          }
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
            label="Process-R gate"
            value={`${(scorecard.stage1WinrateGate * 100).toFixed(0)}% WR slider`}
            hint={`Diagnostic only (recommended ${(scorecard.stage1WinrateRecommended * 100).toFixed(0)}%). Birth pass is median loss R / occupancy / first-touch.`}
            tone="warn"
            className="birth-intel-field-span"
          />
        ) : null}
      </div>
    </div>
  );
}
