import type { BirthProgressPayload, BirthSettingsPayload, BirthStatusPayload } from "@/lib/birthClient";
import { extractBirthSessionHud, extractStageScorecard } from "@/lib/birthPhaseModel";
import type { PPOEvolutionMetric } from "@/lib/ppoEvolutionTypes";
import { cn } from "@/lib/utils";

import { BirthAdvancedPanel, type BirthAdvancedSection } from "@/components/birth/BirthAdvancedPanel";
import { BirthRemediationBar } from "@/components/birth/BirthRemediationBar";
import { BirthStageScorecard } from "@/components/birth/BirthStageScorecard";

interface BirthStageIntelColumnProps {
  progress?: BirthProgressPayload;
  status?: BirthStatusPayload | null;
  running?: boolean;
  finale?: boolean;
  advancedOpen: BirthAdvancedSection | null;
  onToggleAdvanced: (section: BirthAdvancedSection | null) => void;
  settingsInitial?: Partial<BirthSettingsPayload>;
  trainingLogs?: PPOEvolutionMetric[];
  trainingConnected?: boolean;
  className?: string;
}

export function BirthStageIntelColumn({
  progress,
  status = null,
  running = false,
  finale = false,
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

  return (
    <section
      className={cn(
        "birth-stage-intel-column lumina-glass lumina-glass--overlay flex h-full min-h-0 flex-col overflow-hidden",
        className,
      )}
      aria-label="Birth stage intelligence"
    >
      <header className="birth-stage-intel-column__header shrink-0 border-b border-white/8 px-3 py-2">
        <span className="font-mono text-[10px] tracking-wide text-cyan-200/90 uppercase">
          Stage intelligence
        </span>
      </header>
      <div className="birth-stage-intel-column__body min-h-0 flex-1 space-y-2 px-3 py-2">
        {showContent && scorecard ? (
          <BirthStageScorecard
            progress={progress}
            birthRunning={running}
            birthStatus={status?.status}
          />
        ) : showContent && sessionHud ? (
          <div className="birth-stage-prep space-y-2 rounded-lg border border-cyan-500/20 bg-cyan-950/10 p-3">
            <p className="font-mono text-xs font-medium tracking-wide text-foreground">
              Birth preparation
            </p>
            <p className="font-mono text-[10px] text-muted-foreground">{sessionHud.subPhaseLabel}</p>
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
