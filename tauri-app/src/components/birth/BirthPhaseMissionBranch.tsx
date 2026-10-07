import type { BirthAdvancedSection } from "@/components/birth/BirthAdvancedPanel";
import { BirthCommandBar } from "@/components/birth/BirthCommandBar";
import { BirthMissionControl } from "@/components/birth/BirthMissionControl";
import { BirthStageIntelColumn } from "@/components/birth/BirthStageIntelColumn";
import { PhaseMissionFrame } from "@/components/shared/PhaseCinematicFrames";
import type { BirthPhaseDerived } from "@/hooks/useBirthPhaseDerived";
import { cn } from "@/lib/utils";

interface BirthPhaseMissionBranchProps {
  derived: BirthPhaseDerived;
  controlBusy: boolean;
  advancedOpen: BirthAdvancedSection | null;
  onToggleAdvanced: (section: BirthAdvancedSection | null) => void;
  onStop: () => Promise<void>;
}

export function BirthPhaseMissionBranch({
  derived,
  controlBusy,
  advancedOpen,
  onToggleAdvanced,
  onStop,
}: BirthPhaseMissionBranchProps) {
  const {
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
        "relative flex min-h-0 flex-1 flex-col overflow-hidden",
        recoveryOverlayActive && "invisible opacity-0",
      )}
    >
      <BirthCommandBar
        mode="running"
        milestones={milestones}
        progress={status?.progress}
        status={status?.status ?? "idle"}
        busy={controlBusy}
        advancedOpen={advancedOpen}
        onToggleAdvanced={onToggleAdvanced}
        onStop={onStop}
      />
      <PhaseMissionFrame
        activating={helixActivating}
        trainingTrades={targetTrades}
        className={cn(recoveryOverlayActive && "invisible opacity-0")}
        control={
          <BirthMissionControl
            headline={headline}
            subtitle={phaseSubtitle}
            milestones={milestones}
            progress={status?.progress}
            status={status}
            elapsedSeconds={status?.elapsed_seconds}
            progressMessage={status?.progress?.message ?? status?.message}
            finale={false}
            running={running}
            showStopControl
            controlBusy={controlBusy}
            className="min-h-0"
          />
        }
        intel={
          <BirthStageIntelColumn
            progress={status?.progress}
            status={status}
            running={running}
            finale={false}
            resumePlateauRisk={resumePlateauRisk}
            resumePlateauRiskTrades={status?.resume_plateau_risk_trades ?? null}
            advancedOpen={advancedOpen}
            onToggleAdvanced={onToggleAdvanced}
            settingsInitial={birthSettingsInitial}
            trainingLogs={logs}
            trainingConnected={connected}
            className="min-h-0"
          />
        }
      />
    </div>
  );
}
