/**
 * Stage tab — Stage goal checklist (all pass gates) + lean ops tiles.
 * Pass-gate metrics live only in Stage goal (no duplicate full-height cards).
 * EdgeScore lives on the fitness landscape — not repeated here.
 */
import type { BirthProgressPayload } from "@/lib/birthClient";
import { formatBirthChampionEdgeScore } from "@/lib/birth/birthMetricFormat";
import { buildStagePassChecklist } from "@/lib/birth/birthStagePassChecklist";
import { presentBlockerDetail } from "@/lib/birth/birthStageScorecardEdgescore";
import {
  formatSwarmTournamentLiftLabel,
  isSwarmRejectedNoLift,
} from "@/lib/birth/birthTournamentNaming";
import type { StageScorecardModel } from "@/lib/birthPhaseModel";
import { CONDITION_VALUE_TEXT_CLASS } from "@/lib/conditionTone";
import { cn } from "@/lib/utils";
import { BirthFieldCard } from "@/components/birth/BirthFieldCard";
import { BirthStagePassChecklistCard } from "@/components/birth/BirthStagePassChecklistCard";
import { formatDataWindow } from "@/components/birth/BirthStageScorecardFormat";

function BirthBlockerGateCard({
  label,
  detail,
}: {
  label?: string | null;
  detail: string;
}) {
  const presented = presentBlockerDetail(detail);
  return (
    <div
      className="risk-envelope-field-card birth-field-card birth-blocker-gate birth-intel-field-span birth-stage-blocker-compact"
      data-tone="danger"
      title={presented.raw}
    >
      <div className="birth-blocker-gate__head">
        <p className="risk-envelope-field-label mb-0">{label ?? "Blocking metric"}</p>
        <p
          className={cn(
            "birth-blocker-gate__value font-mono tabular-nums tracking-tight",
            CONDITION_VALUE_TEXT_CLASS.danger,
          )}
        >
          {presented.value}
        </p>
      </div>
      <p className="birth-blocker-gate__kicker">{presented.title}</p>
      <p className="risk-envelope-field-hint birth-blocker-gate__hint mb-0">
        {presented.hint}
      </p>
    </div>
  );
}

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
        <BirthBlockerGateCard
          label={scorecard.blockerLabel}
          detail={scorecard.blockerDetail}
        />
      ) : null}

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
        hint={
          scorecard.wallClockTradesPerMin != null
            ? `~${scorecard.wallClockTradesPerMin.toLocaleString()} trades/min`
            : undefined
        }
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
