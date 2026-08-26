import type { BirthProgressPayload, BirthSettingsPayload, BirthStatusPayload } from "@/lib/birthClient";
import { isBirthCurriculumScorecardActive } from "@/lib/birth/birthActiveProgress";
import { extractBirthSessionHud, extractStageScorecard, isStageGoalMet } from "@/lib/birthPhaseModel";
import type { PPOEvolutionMetric } from "@/lib/ppoEvolutionTypes";
import { cn } from "@/lib/utils";

import { BirthAdvancedPanel, type BirthAdvancedSection } from "@/components/birth/BirthAdvancedPanel";
import { BirthFieldCard } from "@/components/birth/BirthFieldCard";
import { BirthRemediationBar } from "@/components/birth/BirthRemediationBar";
import { BirthStageScorecard } from "@/components/birth/BirthStageScorecard";

interface BirthStageIntelColumnProps {
  progress?: BirthProgressPayload;
  status?: BirthStatusPayload | null;
  running?: boolean;
  finale?: boolean;
  resumePlateauRisk?: boolean;
  resumePlateauRiskTrades?: number | null;
  advancedOpen: BirthAdvancedSection | null;
  onToggleAdvanced: (section: BirthAdvancedSection | null) => void;
  settingsInitial?: Partial<BirthSettingsPayload>;
  trainingLogs?: PPOEvolutionMetric[];
  trainingConnected?: boolean;
  className?: string;
}

type ChipState = "ok" | "partial" | "warn" | "idle";

function StatusChip({
  label,
  state,
  tip,
}: {
  label: string;
  state: ChipState;
  tip: string;
}) {
  return (
    <span
      className="risk-envelope-status-chip"
      data-state={state === "idle" ? undefined : state}
      title={tip}
    >
      <span className="risk-envelope-status-chip__dot" />
      {label}
    </span>
  );
}

function resolveIntelChips(progress: BirthProgressPayload | undefined): {
  gate: ChipState;
  health: ChipState;
  recovery: ChipState;
  wall: ChipState;
  tips: Record<"gate" | "health" | "recovery" | "wall", string>;
  stageLabel: string;
} {
  const scorecard = extractStageScorecard(progress);
  const prepActive =
    Boolean(progress) && !scorecard && !isBirthCurriculumScorecardActive(progress);
  const stageLabel = scorecard?.stageLabel
    ? scorecard.stageLabel
    : prepActive
      ? "Birth preparation"
      : "Stage data syncing…";

  let gate: ChipState = "idle";
  let health: ChipState = "idle";
  let recovery: ChipState = "idle";
  let wall: ChipState = "idle";

  if (scorecard) {
    if (scorecard.blockerDetail) {
      gate = "warn";
    } else if (isStageGoalMet(scorecard)) {
      gate = "ok";
    } else if (scorecard.tradesDone > 0) {
      gate = "partial";
    }

    if (scorecard.health === "advancing") health = "ok";
    else if (scorecard.health === "stale") health = "warn";
    else health = "partial";

    if (scorecard.adaptationCycling) {
      recovery = "warn";
    } else if (
      scorecard.stallRemediationCycle != null &&
      scorecard.stallRemediationCycle > 0
    ) {
      recovery = "warn";
    } else if (scorecard.volumeGateStatus === "PASSED") {
      recovery = "ok";
    } else if (
      scorecard.adaptationEnabled &&
      (scorecard.retriesThisStage > 0 || scorecard.volumeGateStatus === "PENDING")
    ) {
      recovery = "partial";
    }

    if (scorecard.stageWallRemainingSec != null) {
      const mins = Math.ceil(scorecard.stageWallRemainingSec / 60);
      wall = mins < 30 ? "warn" : "ok";
    }
  }

  return {
    gate,
    health,
    recovery,
    wall,
    stageLabel,
    tips: {
      gate: scorecard?.blockerDetail
        ? `Blocking: ${scorecard.blockerDetail}`
        : scorecard
          ? "Pass gate status for this curriculum stage"
          : "Awaiting stage gate data",
      health: scorecard?.healthHint ?? "Stage heartbeat / freshness",
      recovery: scorecard?.adaptationCycling
        ? "Recovery cycling — adaptation without train-laps"
        : "Adaptive recovery and stall remediation",
      wall:
        scorecard?.stageWallRemainingSec != null
          ? `${Math.ceil(scorecard.stageWallRemainingSec / 60)}m remaining on stage wall`
          : "Stage wall timer",
    },
  };
}

export function BirthStageIntelColumn({
  progress,
  status = null,
  running = false,
  finale = false,
  resumePlateauRisk = false,
  resumePlateauRiskTrades = null,
  advancedOpen,
  onToggleAdvanced,
  settingsInitial,
  trainingLogs = [],
  trainingConnected = false,
  className,
}: BirthStageIntelColumnProps) {
  const scorecard = extractStageScorecard(progress);
  const sessionHud = extractBirthSessionHud(progress);
  const prepActive =
    Boolean(progress) && !scorecard && !isBirthCurriculumScorecardActive(progress);
  const showContent = (running || finale) && progress;
  const chips = resolveIntelChips(progress);

  return (
    <section
      className={cn(
        "birth-stage-intel-column lumina-glass lumina-glass--overlay flex h-full min-h-0 flex-col overflow-hidden",
        className,
      )}
      aria-label="Birth stage intelligence"
    >
      <header className="birth-stage-intel-column__header risk-envelope-panel__toolbar shrink-0">
        <div className="min-w-0">
          <p className="risk-envelope-panel__toolbar-title">Stage intelligence</p>
          <p className="mt-0.5 font-mono text-[0.5rem] tracking-wide text-white/30 uppercase">
            {chips.stageLabel}
          </p>
        </div>
      </header>

      {showContent && scorecard ? (
        <div
          className="birth-stage-intel-status-strip risk-envelope-status-strip shrink-0"
          role="status"
          aria-label="Stage intelligence status"
        >
          <StatusChip label="GATE" state={chips.gate} tip={chips.tips.gate} />
          <StatusChip label="HEALTH" state={chips.health} tip={chips.tips.health} />
          <StatusChip label="RECOVERY" state={chips.recovery} tip={chips.tips.recovery} />
          <StatusChip label="WALL" state={chips.wall} tip={chips.tips.wall} />
        </div>
      ) : null}

      {showContent && scorecard ? (
        <div className="flex flex-wrap gap-1 px-2.5" aria-label="Foundation physics">
          <StatusChip
            label={`R̃ ${scorecard.medianLossR != null ? scorecard.medianLossR.toFixed(2) : "—"}`}
            state={
              scorecard.medianLossR != null && scorecard.medianLossR <= 1.5 ? "ok" : "warn"
            }
            tip="Median loss R (process health ≤ 1.5)"
          />
          <StatusChip
            label={`occ ${scorecard.occupancy != null ? `${Math.round(scorecard.occupancy * 100)}%` : "—"}`}
            state={scorecard.occupancy != null ? "partial" : "idle"}
            tip="Occupancy (plant-flat, never hold%)"
          />
          <StatusChip
            label={`edge ${scorecard.edgeVsFirstTouch != null ? `${(scorecard.edgeVsFirstTouch * 100).toFixed(1)}pp` : "—"}`}
            state={
              scorecard.edgeVsFirstTouch != null && scorecard.edgeVsFirstTouch >= 0 ? "ok" : "partial"
            }
            tip="Skill WR minus first-touch"
          />
          <StatusChip
            label={`meanR ${scorecard.meanR != null ? scorecard.meanR.toFixed(2) : "—"}`}
            state={scorecard.meanR != null && scorecard.meanR >= 0 ? "ok" : "partial"}
            tip="Mean R (profit is Playground, not Birth pass)"
          />
        </div>
      ) : null}

      <div className="birth-stage-intel-column__body min-h-0 flex-1 space-y-1.5 px-2.5 py-1.5">
        {showContent && scorecard ? (
          <BirthStageScorecard
            progress={progress}
            birthRunning={running}
            birthStatus={status?.status}
            resumePlateauRisk={resumePlateauRisk}
            resumePlateauRiskTrades={resumePlateauRiskTrades}
          />
        ) : showContent && (sessionHud || prepActive) ? (
          <div className="birth-stage-prep space-y-2">
            <p className="font-mono text-[0.55rem] tracking-[0.14em] text-cyan-200/80 uppercase">
              Birth preparation
            </p>
            <p className="text-[11px] leading-relaxed text-cyan-100/55">
              Historical data load and plant bootstrap. Stage 1/5 appears when curriculum training
              starts — not during data prep.
            </p>
            <div className="birth-intel-field-grid">
              <BirthFieldCard
                label="Sub-phase"
                value={
                  sessionHud?.subPhaseLabel ||
                  String(progress?.sub_phase_label || progress?.phase || "—")
                }
              />
              <BirthFieldCard
                label="Patterns mined"
                value={(sessionHud?.patternsMined ?? 0).toLocaleString()}
              />
              <BirthFieldCard
                label="Learning attempt"
                value={
                  sessionHud && sessionHud.learningAttempt > 0
                    ? String(sessionHud.learningAttempt)
                    : "—"
                }
              />
            </div>
          </div>
        ) : showContent ? (
          <p className="text-xs text-muted-foreground">Stage data syncing…</p>
        ) : null}

        {showContent && status ? <BirthRemediationBar status={status} /> : null}

        <BirthAdvancedPanel
          running={running}
          openSection={advancedOpen}
          onToggleSection={onToggleAdvanced}
          settingsInitial={settingsInitial}
          trainingLogs={trainingLogs}
          trainingConnected={trainingConnected}
          controlled={running}
        />
      </div>
    </section>
  );
}
