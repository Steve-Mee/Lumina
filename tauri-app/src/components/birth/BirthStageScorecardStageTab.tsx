/**
 * Stage tab — Stage goal checklist (all pass gates) + lean ops tiles.
 * Pass-gate metrics live only in Stage goal (no duplicate full-height cards).
 */
import type { BirthProgressPayload } from "@/lib/birthClient";
import { formatBirthChampionEdgeScore } from "@/lib/birth/birthMetricFormat";
import { buildStagePassChecklist } from "@/lib/birth/birthStagePassChecklist";
import {
  formatSwarmTournamentLiftLabel,
  isSwarmRejectedNoLift,
} from "@/lib/birth/birthTournamentNaming";
import type { StageScorecardModel } from "@/lib/birthPhaseModel";
import { BirthFieldCard } from "@/components/birth/BirthFieldCard";
import { BirthStagePassChecklistCard } from "@/components/birth/BirthStagePassChecklistCard";
import {
  edgeScoreConditionTone,
  formatDataWindow,
  formatMetricTarget,
  formatMetricValue,
  isGoalMet,
} from "@/components/birth/BirthStageScorecardFormat";

export function StageTabFields({
  scorecard,
  progress,
}: {
  scorecard: StageScorecardModel;
  progress?: BirthProgressPayload;
}) {
  const passChecklist = buildStagePassChecklist(scorecard, progress);
  const heartbeatLabel =
    scorecard.heartbeatSec != null
      ? `${scorecard.heartbeatSec}s ago`
      : "Awaiting update";
  const passMetricHint = formatMetricTarget(scorecard);
  const dataHint =
    scorecard.wallClockTradesPerMin != null
      ? `~${scorecard.wallClockTradesPerMin.toLocaleString()} trades/min`
      : undefined;
  const goalMet = isGoalMet(scorecard);
  const edgeTone = edgeScoreConditionTone(scorecard, { goalMet });
  const champion = formatBirthChampionEdgeScore(progress ?? {});
  const swarmReject = isSwarmRejectedNoLift(progress);
  const tournamentLift = formatSwarmTournamentLiftLabel(progress);
  const showTournamentLift =
    swarmReject ||
    progress?.policy_swarm_active === true ||
    progress?.swarm_tournament_lift_ok === true ||
    progress?.swarm_edgescore_lift_ok === true ||
    progress?.swarm_champion_accepted === true;

  const budget =
    scorecard.stageBudgetTrades ?? progress?.stage_budget_trades ?? null;

  return (
    <div className="birth-intel-field-grid birth-stage-tab-fields">
      {passChecklist ? <BirthStagePassChecklistCard checklist={passChecklist} /> : null}

      {scorecard.blockerDetail ? (
        <BirthFieldCard
          label={scorecard.blockerLabel ?? "Blocking metric"}
          value={scorecard.blockerDetail}
          hint="Primary fail gate"
          tone="danger"
          className="birth-intel-field-span birth-stage-blocker-compact"
        />
      ) : null}

      {/* Composite score — detail; individual gates are in Stage goal only */}
      <BirthFieldCard
        label="EdgeScore"
        value={formatMetricValue(scorecard)}
        hint={passMetricHint || undefined}
        tone={edgeTone}
        tip="Composite of the Stage goal gates (not the champion freeze)."
      />
      <BirthFieldCard
        label="Champion"
        value={champion.value}
        hint={champion.hint}
        tone={champion.tone}
        tip="Best frozen EdgeScore after pass-gate volume."
      />
      {showTournamentLift ? (
        <BirthFieldCard
          label="Tournament"
          value={tournamentLift.value}
          hint={tournamentLift.hint}
          tone={tournamentLift.tone}
        />
      ) : null}
      <BirthFieldCard
        label="Sub-phase"
        value={scorecard.subPhaseLabel}
        hint={
          scorecard.explorationActive
            ? "Exploration active"
            : heartbeatLabel !== "Awaiting update"
              ? heartbeatLabel
              : budget != null
                ? `budget ${Number(budget).toLocaleString()}`
                : undefined
        }
        tone={
          scorecard.health === "stale"
            ? "warn"
            : scorecard.health === "advancing"
              ? "ok"
              : "default"
        }
      />
      <BirthFieldCard
        label="Data window"
        value={formatDataWindow(scorecard)}
        hint={dataHint}
      />
      {scorecard.provisionalPass ? (
        <BirthFieldCard
          label="Pass mode"
          value="Provisional"
          hint="Practice only"
          tone="warn"
        />
      ) : null}
    </div>
  );
}
