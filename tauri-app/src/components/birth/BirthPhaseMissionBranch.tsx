import { lazy, Suspense } from "react";

import type { BirthAdvancedSection } from "@/components/birth/BirthAdvancedPanel";
import { BirthCommandBar } from "@/components/birth/BirthCommandBar";
import { BirthMissionControl } from "@/components/birth/BirthMissionControl";
import { BirthOrganismVisual } from "@/components/birth/BirthOrganismVisual";
import { BirthStageIntelColumn } from "@/components/birth/BirthStageIntelColumn";
import type { BirthPhaseDerived } from "@/hooks/useBirthPhaseDerived";
import { cn } from "@/lib/utils";

const BirthHelixVisual = lazy(() =>
  import("@/components/birth/BirthHelixVisual").then((module) => ({
    default: module.BirthHelixVisual,
  })),
);

interface BirthPhaseMissionBranchProps {
  derived: BirthPhaseDerived;
  controlBusy: boolean;
  advancedOpen: BirthAdvancedSection | null;
  onToggleAdvanced: (section: BirthAdvancedSection | null) => void;
  onStop: () => Promise<void>;
  onEnterDeck: () => void;
  onExtraTraining: () => void;
}

export function BirthPhaseMissionBranch({
  derived,
  controlBusy,
  advancedOpen,
  onToggleAdvanced,
  onStop,
  onEnterDeck,
  onExtraTraining,
}: BirthPhaseMissionBranchProps) {
  const {
    awakening,
    recoveryOverlayActive,
    milestones,
    status,
    headline,
    phaseSubtitle,
    running,
    helixActivating,
    targetTrades,
    resumePlateauRisk,
    birthSettingsInitial,
    logs,
    connected,
  } = derived;

  return (
    <div
      className={cn(
        "birth-mission-shell relative flex min-h-0 flex-1 flex-col overflow-hidden",
        awakening && "birth-finale-lock",
        recoveryOverlayActive && "invisible opacity-0",
      )}
    >
      <BirthCommandBar
        mode={awakening ? "finale" : "running"}
        milestones={milestones}
        progress={status?.progress}
        status={status?.status ?? "idle"}
        busy={controlBusy}
        advancedOpen={advancedOpen}
        onToggleAdvanced={onToggleAdvanced}
        onStop={onStop}
        onEnterDeck={onEnterDeck}
        onExtraTraining={onExtraTraining}
      />
      <div className="birth-mission-grid min-h-0 flex-1 overflow-hidden p-3 md:p-4">
        <div className="birth-helix-accent-wrap pointer-events-none hidden min-h-0 lg:block">
          <Suspense
            fallback={
              <div className="flex h-full items-center justify-center">
                <BirthOrganismVisual className="size-16 opacity-80" />
              </div>
            }
          >
            <BirthHelixVisual
              activating={helixActivating}
              ceremonyMode
              trainingTrades={targetTrades}
              className="birth-helix-accent max-h-full w-full max-w-full"
            />
          </Suspense>
        </div>
        <BirthMissionControl
          headline={awakening ? "Birth complete" : headline}
          subtitle={
            awakening
              ? "Your organism is trained and ready for the command deck."
              : phaseSubtitle
          }
          milestones={milestones}
          progress={status?.progress}
          status={status}
          elapsedSeconds={status?.elapsed_seconds}
          progressMessage={status?.progress?.message ?? status?.message}
          finale={awakening}
          running={running}
          showStopControl
          controlBusy={controlBusy}
          className="min-h-0"
        />
        <BirthStageIntelColumn
          progress={status?.progress}
          status={status}
          running={running}
          finale={awakening}
          resumePlateauRisk={resumePlateauRisk}
          resumePlateauRiskTrades={status?.resume_plateau_risk_trades ?? null}
          advancedOpen={advancedOpen}
          onToggleAdvanced={onToggleAdvanced}
          settingsInitial={birthSettingsInitial}
          trainingLogs={logs}
          trainingConnected={connected}
          className="min-h-0"
        />
      </div>
    </div>
  );
}
