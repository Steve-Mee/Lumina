import type { ReactNode } from "react";
import { FileText, Settings2, Zap } from "lucide-react";

import type { BirthAdvancedSection } from "@/components/birth/BirthAdvancedPanel";
import { BirthMilestoneTrack } from "@/components/birth/BirthMilestoneTrack";
import { Button } from "@/components/ui/button";
import type { BirthProgressPayload } from "@/lib/birthClient";
import type { BirthMilestone } from "@/lib/birthPhaseModel";
import { buildHudMilestones } from "@/lib/birthPhaseModel";
import { luminaInteractiveClass } from "@/lib/glassGlowTaxonomy";
import { cn } from "@/lib/utils";

type BirthCommandBarMode = "running" | "genesis" | "finale";

interface BirthCommandBarProps {
  mode: BirthCommandBarMode;
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

function AdvancedToggleButton({
  label,
  active,
  onClick,
  icon,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
  icon: ReactNode;
}) {
  return (
    <Button
      type="button"
      variant="ghost"
      size="sm"
      className={cn(
        luminaInteractiveClass("ghost"),
        "birth-command-bar__tool-btn",
        active && "birth-command-bar__tool-btn--active",
      )}
      aria-pressed={active}
      onClick={onClick}
    >
      {icon}
      <span>{label}</span>
    </Button>
  );
}

function RunningAdvancedActions({
  advancedOpen,
  onToggleAdvanced,
}: {
  advancedOpen: BirthAdvancedSection | null;
  onToggleAdvanced?: (section: BirthAdvancedSection | null) => void;
}) {
  const toggle = (section: BirthAdvancedSection) => {
    onToggleAdvanced?.(advancedOpen === section ? null : section);
  };

  return (
    <div className="birth-command-bar__actions" role="group" aria-label="Birth advanced panels">
      <AdvancedToggleButton
        label="Logs"
        active={advancedOpen === "logs"}
        onClick={() => toggle("logs")}
        icon={<FileText className="size-3.5 shrink-0" aria-hidden />}
      />
      <AdvancedToggleButton
        label="Settings"
        active={advancedOpen === "settings"}
        onClick={() => toggle("settings")}
        icon={<Settings2 className="size-3.5 shrink-0" aria-hidden />}
      />
      <AdvancedToggleButton
        label="PPO"
        active={advancedOpen === "training"}
        onClick={() => toggle("training")}
        icon={<Zap className="size-3.5 shrink-0" aria-hidden />}
      />
    </div>
  );
}

export function BirthCommandBar({
  mode,
  milestones: _milestones = [],
  progress,
  status = "idle",
  checkpointAvailable: _checkpointAvailable = false,
  busy: _busy = false,
  advancedOpen = null,
  onToggleAdvanced,
  onStop: _onStop,
  onStart: _onStart,
  onWipe: _onWipe,
  onResumeCheckpoint: _onResumeCheckpoint,
  onEnterDeck,
  onExtraTraining,
  className,
}: BirthCommandBarProps) {
  const hudMilestones = buildHudMilestones(progress, status);
  const showMilestoneRail = mode === "running" || mode === "finale";

  return (
    <header
      className={cn(
        "birth-command-bar pointer-events-auto relative z-30 lumina-glass lumina-glass--panel shrink-0 border-b border-white/10",
        className,
      )}
      role="banner"
      aria-label="Birth mission HUD"
    >
      <div className="birth-command-bar__accent deck-panel-accent absolute inset-x-0 top-0 h-px origin-left" />
      <div className="birth-command-bar__row min-h-0 px-3 py-1.5 md:px-4">
        {showMilestoneRail ? (
          <div className="birth-command-bar__milestones">
            <BirthMilestoneTrack
              milestones={hudMilestones.items}
              upcomingCount={0}
              variant="bar"
            />
          </div>
        ) : (
          <div className="min-w-0 flex-1" />
        )}

        {mode === "running" ? (
          <RunningAdvancedActions
            advancedOpen={advancedOpen}
            onToggleAdvanced={onToggleAdvanced}
          />
        ) : null}

        {mode === "finale" ? (
          <div className="birth-command-bar__actions">
            <Button
              type="button"
              className="onboarding-cta h-7 min-w-[132px] px-3 py-1 font-mono text-[10px] tracking-wide uppercase"
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
                "h-7 font-mono text-[10px] tracking-wide uppercase text-muted-foreground",
              )}
              onClick={onExtraTraining}
            >
              Extra training
            </Button>
          </div>
        ) : null}
      </div>
    </header>
  );
}
