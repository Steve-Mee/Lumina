import { Activity, X } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { useState } from "react";
import { createPortal } from "react-dom";

import { BirthCompletionSummary } from "@/components/birth/BirthCompletionSummary";
import { BirthLogsPanel } from "@/components/birth/BirthLogsPanel";
import { BirthMetricsStrip } from "@/components/birth/BirthMetricsStrip";
import { BirthMilestoneTrack } from "@/components/birth/BirthMilestoneTrack";
import { BirthSettingsPanel } from "@/components/birth/BirthSettingsPanel";
import { BirthStageScorecard } from "@/components/birth/BirthStageScorecard";
import { TrainingControlBar } from "@/components/operations/TrainingControlBar";
import { PPOEvolutionDashboard } from "@/components/ppo/PPOEvolutionDashboard";
import { Button } from "@/components/ui/button";
import { usePrefersReducedMotion } from "@/hooks/usePrefersReducedMotion";
import { useOnboardingModeMotion } from "@/hooks/useOnboardingModeMotion";
import { distressPanelClass } from "@/lib/modePresentation";
import { transitionOrNone } from "@/lib/motionPresets";
import type {
  BirthSettingsPayload,
  BirthProgressPayload,
  BirthStatusPayload,
} from "@/lib/birthClient";
import type { BirthMilestone } from "@/lib/birthPhaseModel";
import { buildCompactMilestones } from "@/lib/birthPhaseModel";
import type { PPOEvolutionMetric } from "@/lib/ppoEvolutionTypes";
import { cn } from "@/lib/utils";

type DiagnosticsPanel = "progress" | "settings" | "logs" | "training";

interface BirthDiagnosticsDrawerProps {
  running: boolean;
  finale?: boolean;
  defaultOpen?: boolean;
  milestones?: BirthMilestone[];
  progress?: BirthProgressPayload;
  elapsedSeconds?: number;
  progressMessage?: string;
  birthStatus?: BirthStatusPayload | null;
  settingsInitial?: Partial<BirthSettingsPayload>;
  trainingLogs?: PPOEvolutionMetric[];
  trainingConnected?: boolean;
  showStop?: boolean;
  onStop?: () => void;
  className?: string;
}

export function BirthDiagnosticsDrawer({
  running,
  finale = false,
  defaultOpen = false,
  milestones: _milestones = [],
  progress,
  elapsedSeconds,
  progressMessage,
  birthStatus = null,
  settingsInitial,
  trainingLogs = [],
  trainingConnected = false,
  showStop = false,
  onStop,
  className,
}: BirthDiagnosticsDrawerProps) {
  const reducedMotion = usePrefersReducedMotion();
  const modeMotion = useOnboardingModeMotion();
  const [open, setOpen] = useState(defaultOpen);
  const [panel, setPanel] = useState<DiagnosticsPanel>("progress");
  const showTraining = running || trainingLogs.length > 0 || trainingConnected;
  const compactMilestones = buildCompactMilestones(progress, birthStatus?.status ?? "idle");

  const drawerOverlay =
    typeof document !== "undefined"
      ? createPortal(
          <AnimatePresence>
            {open ? (
              <>
                <motion.button
                  type="button"
                  className="subsystems-drawer-scrim birth-diagnostics-backdrop backdrop-blur-md"
                  aria-label="Close telemetry"
                  initial={reducedMotion ? false : { opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  transition={transitionOrNone(reducedMotion, modeMotion)}
                  onClick={() => setOpen(false)}
                />
                <motion.aside
                  id="birth-diagnostics-panel"
                  role="dialog"
                  aria-label={finale ? "Birth training summary" : "Birth telemetry"}
                  data-mode="SIM"
                  className="birth-diagnostics-panel subsystems-drawer-airlock lumina-glass lumina-glass--overlay"
                  initial={reducedMotion ? false : { x: "100%" }}
                  animate={{ x: 0 }}
                  exit={reducedMotion ? undefined : { x: "100%" }}
                  transition={transitionOrNone(reducedMotion, modeMotion)}
                >
                  <div className="relative flex items-center justify-between border-b border-white/10 px-4 py-3">
                    <div className="deck-panel-accent absolute inset-x-4 top-0 h-px origin-left" />
                    <div>
                      <p className="font-mono text-xs tracking-[0.14em] text-foreground uppercase">
                        {finale ? "Birth training summary" : "Birth telemetry"}
                      </p>
                      <p className="mt-0.5 font-mono text-[10px] text-muted-foreground">
                        T3 diagnostics airlock
                      </p>
                    </div>
                    <button
                      type="button"
                      className="rounded-md p-1.5 text-muted-foreground hover:bg-white/5 hover:text-foreground"
                      onClick={() => setOpen(false)}
                      aria-label="Close"
                    >
                      <X className="size-4" />
                    </button>
                  </div>

                  <div className="flex flex-wrap gap-2 border-b border-white/5 px-4 py-3">
                    <button
                      type="button"
                      className={cn(
                        "birth-diagnostics-tab",
                        panel === "progress" && "birth-diagnostics-tab--active",
                      )}
                      onClick={() => setPanel("progress")}
                    >
                      Progress
                    </button>
                    {showTraining ? (
                      <button
                        type="button"
                        className={cn(
                          "birth-diagnostics-tab",
                          panel === "training" && "birth-diagnostics-tab--active",
                        )}
                        onClick={() => setPanel("training")}
                      >
                        Training
                      </button>
                    ) : null}
                    <button
                      type="button"
                      className={cn(
                        "birth-diagnostics-tab",
                        panel === "settings" && "birth-diagnostics-tab--active",
                      )}
                      onClick={() => setPanel("settings")}
                    >
                      Settings{running ? " (locked)" : ""}
                    </button>
                    <button
                      type="button"
                      className={cn(
                        "birth-diagnostics-tab",
                        panel === "logs" && "birth-diagnostics-tab--active",
                      )}
                      onClick={() => setPanel("logs")}
                    >
                      Logs
                    </button>
                  </div>

                  <div className="flex-1 overflow-y-auto px-4 py-4">
                    {panel === "progress" ? (
                      <div className="space-y-4">
                        {finale && birthStatus ? (
                          <BirthCompletionSummary status={birthStatus} />
                        ) : null}
                        <BirthMilestoneTrack
                          milestones={compactMilestones.items}
                          upcomingCount={compactMilestones.upcomingCount}
                          variant="drawer"
                        />
                        {(running || finale) && progress ? (
                          <>
                            <BirthStageScorecard progress={progress} />
                            <BirthMetricsStrip
                              progress={progress}
                              elapsedSeconds={elapsedSeconds}
                              message={progressMessage}
                            />
                          </>
                        ) : null}
                      </div>
                    ) : null}
                    {panel === "training" ? (
                      <div className="space-y-3">
                        <TrainingControlBar compact className="justify-start" />
                        <PPOEvolutionDashboard
                          logs={trainingLogs}
                          connected={trainingConnected}
                          title="PPO Evolution Dashboard"
                          compact
                        />
                      </div>
                    ) : null}
                    {panel === "settings" ? (
                      <>
                        {running ? (
                          <p className={cn("mb-3 text-xs", distressPanelClass("warn"))}>
                            Settings lock while training runs.
                          </p>
                        ) : null}
                        <BirthSettingsPanel initial={settingsInitial} />
                      </>
                    ) : null}
                    {panel === "logs" ? <BirthLogsPanel /> : null}
                  </div>

                  {showStop && onStop ? (
                    <div className="birth-diagnostics-footer border-t border-white/5 px-4 py-3">
                      <Button
                        type="button"
                        variant="destructive"
                        size="sm"
                        className="w-full font-mono text-[10px] tracking-wide uppercase"
                        onClick={onStop}
                      >
                        Stop birth phase
                      </Button>
                    </div>
                  ) : null}
                </motion.aside>
              </>
            ) : null}
          </AnimatePresence>,
          document.body,
        )
      : null;

  return (
    <div className={cn("birth-diagnostics pointer-events-auto", className)}>
      <button
        type="button"
        className="birth-diagnostics-trigger deck-tab-chip lumina-glass lumina-glass--panel"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-controls="birth-diagnostics-panel"
      >
        <Activity className="size-3.5" aria-hidden />
        {finale ? "Training summary" : "Telemetry"}
      </button>
      {drawerOverlay}
    </div>
  );
}
