import type { BirthProgressPayload, BirthStatusPayload } from "@/lib/birthClient";

import type { BirthMilestone } from "@/lib/birthPhaseModel";

import { extractBirthSessionHud, extractStageScorecard } from "@/lib/birthPhaseModel";

import { cn } from "@/lib/utils";



import { BirthBlockerAlert } from "@/components/birth/BirthBlockerAlert";

import { BirthCompletionSummary } from "@/components/birth/BirthCompletionSummary";

import { BirthKpiTile } from "@/components/birth/BirthKpiTile";

import { BirthMetricsStrip } from "@/components/birth/BirthMetricsStrip";



interface BirthMissionControlProps {

  headline: string;

  subtitle: string;

  milestones: BirthMilestone[];

  progress?: BirthProgressPayload;

  status?: BirthStatusPayload | null;

  elapsedSeconds?: number;

  progressMessage?: string;

  finale?: boolean;

  running?: boolean;

  className?: string;

}



function formatMetricValue(scorecard: NonNullable<ReturnType<typeof extractStageScorecard>>): string {

  if (scorecard.metricValue == null) {

    return scorecard.tradesDone > 0 ? "syncing…" : "—";

  }

  if (scorecard.passCriteriaId === "mixed_constitution") {

    return String(Math.round(scorecard.metricValue));

  }

  return `${(scorecard.metricValue * 100).toFixed(0)}%`;

}



function formatMetricTarget(scorecard: NonNullable<ReturnType<typeof extractStageScorecard>>): string {

  if (scorecard.metricTarget != null) {

    return `need ${(scorecard.metricTarget * 100).toFixed(0)}%`;

  }

  return scorecard.goalLabel;

}



function resolveOverallPhaseLabel(progress: BirthProgressPayload | undefined): string {

  const phase = String(progress?.phase ?? "").trim().toLowerCase();

  if (phase === "loading_history") return "Data load";

  if (phase === "enriching_news" || phase === "enriching_regimes") return "Regime map";

  if (phase === "train_holdout_split" || phase === "holdout_preflight") return "Preflight";

  if (phase === "policy_init" || phase === "ticks_ready") return "Policy init";

  if (phase.includes("curriculum") || phase.includes("simulation") || phase === "ppo_training") {

    return "Curriculum";

  }

  if (phase === "ppo_polish" || phase === "oos_evaluation") return "Polish / OOS";

  return "Birth progress";

}



export function BirthMissionControl({

  subtitle,

  milestones: _milestones,

  progress,

  status = null,

  elapsedSeconds,

  progressMessage,

  finale = false,

  running = false,

  className,

}: BirthMissionControlProps) {

  const scorecard = extractStageScorecard(progress);
  const sessionHud = extractBirthSessionHud(progress);
  const overallPct = Number(progress?.progress_pct ?? 0);



  const wallMinutes =

    scorecard?.stageWallRemainingSec != null

      ? Math.ceil(scorecard.stageWallRemainingSec / 60)

      : null;



  const metricTone =

    scorecard?.blockerDetail != null

      ? "warn"

      : scorecard?.metricValue != null &&

          scorecard.metricTarget != null &&

          scorecard.metricValue >= scorecard.metricTarget

        ? "success"

        : "accent";



  return (

    <section

      className={cn(

        "birth-mission-control lumina-glass lumina-glass--overlay flex h-full min-h-0 flex-col overflow-hidden",

        className,

      )}

      aria-label="Birth mission control"

    >

      {finale ? (

        <header className="birth-mission-control__header shrink-0 border-b border-white/8 px-3 py-2">

          <p className="birth-phase-subtitle max-w-prose text-sm">{subtitle}</p>

        </header>

      ) : null}



      <div className="birth-mission-control__body min-h-0 flex-1 overflow-hidden">

        <div className="flex flex-col gap-2 px-3 py-2">

          {finale && status ? <BirthCompletionSummary status={status} /> : null}



          {!finale && subtitle ? (

            <p className="birth-phase-subtitle shrink-0 truncate text-xs text-muted-foreground">{subtitle}</p>

          ) : null}



          <div className="birth-kpi-grid grid shrink-0 grid-cols-2 gap-2">

            <BirthKpiTile

              label="Overall"

              value={`${overallPct.toFixed(1)}%`}

              detail={resolveOverallPhaseLabel(progress)}

              tone="accent"

            />

            <BirthKpiTile

              label={scorecard ? "Stage trades" : "Trades"}

              value={

                scorecard

                  ? `${scorecard.tradesDone.toLocaleString()}`

                  : String(progress?.cumulative_trades ?? 0)

              }

              detail={

                scorecard && scorecard.tradesRequired > 0

                  ? `/ ${scorecard.tradesRequired.toLocaleString()} required`

                  : undefined

              }

            />

            <BirthKpiTile

              label={scorecard?.metricLabel ?? "Pass metric"}

              value={scorecard ? formatMetricValue(scorecard) : "—"}

              detail={scorecard ? formatMetricTarget(scorecard) : undefined}

              tone={metricTone as "default" | "success" | "warn" | "accent"}

            />

            <BirthKpiTile

              label="Stage wall"

              value={wallMinutes != null ? `${wallMinutes}m` : "—"}

              detail={

                scorecard?.learningAttempt

                  ? `attempt ${scorecard.learningAttempt}`

                  : sessionHud?.learningAttempt

                    ? `attempt ${sessionHud.learningAttempt}`

                    : scorecard?.subPhaseLabel ?? sessionHud?.subPhaseLabel

              }

              tone={wallMinutes != null && wallMinutes < 30 ? "warn" : "default"}

            />

          </div>



          {(running || finale) && progress ? (

            <BirthMetricsStrip

              progress={progress}

              elapsedSeconds={elapsedSeconds}

              message={progressMessage}

              twinObservability={status?.twin_observability ?? null}

              embedded

            />

          ) : null}



          {(running || finale) && progress ? <BirthBlockerAlert progress={progress} /> : null}

        </div>

      </div>

    </section>

  );

}

