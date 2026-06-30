import { FileText, Settings2, Zap } from "lucide-react";

import type { BirthAdvancedSection } from "@/components/birth/BirthAdvancedPanel";
import { BirthControlDock, type BirthControlMode } from "@/components/birth/BirthControlDock";
import { BirthMilestoneTrack } from "@/components/birth/BirthMilestoneTrack";
import { Button } from "@/components/ui/button";
import type { BirthProgressPayload } from "@/lib/birthClient";
import type { BirthMilestone } from "@/lib/birthPhaseModel";
import { buildCompactMilestones } from "@/lib/birthPhaseModel";
import { luminaInteractiveClass } from "@/lib/glassGlowTaxonomy";
import { cn } from "@/lib/utils";

interface BirthCommandBarProps {
  mode: BirthControlMode | "finale";
  milestones?: BirthMilestone[];
  progress?: BirthProgressPayload;
  status?: string;
  checkpointAvailable?: boolean;
  busy?: boolean;
  advancedOpen?: BirthAdvancedSection | null;
  onToggleAdvanced?: (section: BirthAdvancedSection | null) => void;
  onStop?: () => void;
  onStart?: () => void;
  onWipe?: () => void;
  onResumeCheckpoint?: () => void;
  onEnterDeck?: () => void;
  onExtraTraining?: () => void;
  className?: string;
}

function RunningAdvancedActions({
  advancedOpen,
  onToggleAdvanced,
  busy,
  onStop,
}: {
  advancedOpen: BirthAdvancedSection | null;
  onToggleAdvanced?: (section: BirthAdvancedSection | null) => void;
  busy?: boolean;
  onStop?: () => void;
}) {
  const toggle = (section: BirthAdvancedSection) => {
    onToggleAdvanced?.(advancedOpen === section ? null : section);
  };

  return (
    <div className="birth-command-bar__actions flex shrink-0 items-center gap-3">
      <div className="birth-command-bar__action-group flex shrink-0 flex-nowrap items-center gap-2">
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className={cn(
            luminaInteractiveClass("ghost"),
            "birth-command-bar__action-btn h-8 gap-1.5 rounded-md border border-white/10 px-2.5 font-mono text-[10px] tracking-wide uppercase",
            advancedOpen === "logs" && "bg-white/10",
          )}
          onClick={() => toggle("logs")}
        >
          <FileText className="size-3.5 shrink-0" aria-hidden />
          <span className="hidden sm:inline">Logs</span>
        </Button>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className={cn(
            luminaInteractiveClass("ghost"),
            "birth-command-bar__action-btn h-8 gap-1.5 rounded-md border border-white/10 px-2.5 font-mono text-[10px] tracking-wide uppercase",
            advancedOpen === "settings" && "bg-white/10",
          )}
          onClick={() => toggle("settings")}
        >
          <Settings2 className="size-3.5 shrink-0" aria-hidden />
          <span className="hidden sm:inline">Settings</span>
        </Button>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className={cn(
            luminaInteractiveClass("ghost"),
            "birth-command-bar__action-btn h-8 gap-1.5 rounded-md border border-white/10 px-2.5 font-mono text-[10px] tracking-wide uppercase",
            advancedOpen === "training" && "bg-white/10",
          )}
          onClick={() => toggle("training")}
        >
          <Zap className="size-3.5 shrink-0" aria-hidden />
          <span className="hidden sm:inline">PPO</span>
        </Button>
      </div>
      <BirthControlDock
        mode="running"
        busy={busy}
        onStop={onStop}
        inline
        className="border-0 bg-transparent p-0 shadow-none backdrop-blur-none"
      />
    </div>
  );
}

export function BirthCommandBar({
  mode,
  milestones: _milestones = [],
  progress,
  status = "idle",
  checkpointAvailable = false,
  busy = false,
  advancedOpen = null,
  onToggleAdvanced,
  onStop,
  onStart,
  onWipe,
  onResumeCheckpoint,
  onEnterDeck,
  onExtraTraining,
  className,
}: BirthCommandBarProps) {
  const compactMilestones = buildCompactMilestones(progress, status);
  const showMilestoneRail = mode === "running" || mode === "finale";

  return (
    <header
      className={cn(
        "birth-command-bar pointer-events-auto relative lumina-glass lumina-glass--panel shrink-0 border-b border-white/10",
        className,
      )}
      role="banner"
    >
      <div className="birth-command-bar__accent deck-panel-accent absolute inset-x-0 top-0 h-px origin-left" />
      <div className="birth-command-bar__top flex items-center justify-end gap-3 px-3 py-2 md:px-4">
        {mode === "running" ? (
          <RunningAdvancedActions
            advancedOpen={advancedOpen}
            onToggleAdvanced={onToggleAdvanced}
            busy={busy}
            onStop={onStop}
          />
        ) : null}
        {mode === "finale" ? (
          <div className="birth-command-bar__actions flex shrink-0 flex-nowrap items-center gap-2">
            <Button
              type="button"
              className="onboarding-cta h-8 min-w-[140px] px-3 py-1 font-mono text-[10px] tracking-wide uppercase"
              onClick={onEnterDeck}
            >
              Enter command deck
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className={cn(
                luminaInteractiveClass("ghost"),
                "h-8 font-mono text-[10px] tracking-wide uppercase text-muted-foreground",
              )}
              onClick={onExtraTraining}
            >
              Extra training
            </Button>
          </div>
        ) : null}
      </div>
      {showMilestoneRail ? (
        <div className="birth-command-bar__milestones border-t border-white/5 px-3 py-1.5 md:px-4">
          <BirthMilestoneTrack
            milestones={compactMilestones.items}
            upcomingCount={compactMilestones.upcomingCount}
            variant="bar"
          />
        </div>
      ) : null}
    </header>
  );
}
