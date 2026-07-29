import type { BirthProgressPayload, BirthSettingsPayload, BirthStatusPayload } from "@/lib/birthClient";
import { extractBirthSessionHud, extractStageScorecard } from "@/lib/birthPhaseModel";
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
  const stageLabel = scorecard?.stageLabel ?? "Stage data syncing…";

  let gate: ChipState = "idle";
  let health: ChipState = "idle";
  let recovery: ChipState = "idle";
  let wall: ChipState = "idle";

  if (scorecard) {
    const edgeScore =
      scorecard.passCriteriaId === "trend_edgescore" ||
      scorecard.passCriteriaId === "range_edgescore" ||
      scorecard.passCriteriaId === "mixed_edgescore";
    if (scorecard.blockerDetail) {
      gate = "warn";
    } else if (edgeScore) {
      // Composite pass: green only when volume gate met and no blocker.
      gate =
        scorecard.tradesRequired > 0 && scorecard.tradesDone >= scorecard.tradesRequired
          ? "ok"
          : scorecard.tradesDone > 0
            ? "partial"
            : "idle";
    } else if (
      scorecard.metricValue != null &&
      scorecard.metricTarget != null &&
      scorecard.metricValue >= scorecard.metricTarget
    ) {
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

      <div className="birth-stage-intel-column__body min-h-0 flex-1 space-y-1.5 px-2.5 py-1.5">
        {showContent && scorecard ? (
          <BirthStageScorecard
            progress={progress}
            birthRunning={running}
            birthStatus={status?.status}
            resumePlateauRisk={resumePlateauRisk}
            resumePlateauRiskTrades={resumePlateauRiskTrades}
          />
        ) : showContent && sessionHud ? (
          <div className="birth-stage-prep space-y-2">
            <p className="font-mono text-[0.55rem] tracking-[0.14em] text-cyan-200/80 uppercase">
              Birth preparation
            </p>
            <div className="birth-intel-field-grid">
              <BirthFieldCard label="Sub-phase" value={sessionHud.subPhaseLabel} />
              <BirthFieldCard
                label="Patterns mined"
                value={sessionHud.patternsMined.toLocaleString()}
              />
              <BirthFieldCard
                label="Learning attempt"
                value={sessionHud.learningAttempt > 0 ? String(sessionHud.learningAttempt) : "—"}
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
