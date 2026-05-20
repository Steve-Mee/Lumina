import { Settings2, X } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { useState } from "react";

import { BirthLogsPanel } from "@/components/birth/BirthLogsPanel";
import { BirthSettingsPanel } from "@/components/birth/BirthSettingsPanel";
import { TrainingControlBar } from "@/components/operations/TrainingControlBar";
import { PPOEvolutionDashboard } from "@/components/ppo/PPOEvolutionDashboard";
import { usePrefersReducedMotion } from "@/hooks/usePrefersReducedMotion";
import { distressPanelClass } from "@/lib/modePresentation";
import type { BirthSettingsPayload } from "@/lib/birthClient";
import type { PPOEvolutionMetric } from "@/lib/ppoEvolutionMetrics";
import { cn } from "@/lib/utils";

type DiagnosticsPanel = "settings" | "logs" | "training";

interface BirthDiagnosticsDrawerProps {
  running: boolean;
  settingsInitial?: Partial<BirthSettingsPayload>;
  trainingLogs?: PPOEvolutionMetric[];
  trainingConnected?: boolean;
  className?: string;
}

export function BirthDiagnosticsDrawer({
  running,
  settingsInitial,
  trainingLogs = [],
  trainingConnected = false,
  className,
}: BirthDiagnosticsDrawerProps) {
  const reducedMotion = usePrefersReducedMotion();
  const [open, setOpen] = useState(false);
  const [panel, setPanel] = useState<DiagnosticsPanel>("training");
  const showTraining = running || trainingLogs.length > 0 || trainingConnected;

  return (
    <div className={cn("birth-diagnostics", className)}>
      <button
        type="button"
        className="birth-diagnostics-trigger"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-controls="birth-diagnostics-panel"
      >
        <Settings2 className="size-3.5" aria-hidden />
        Diagnostics
      </button>

      <AnimatePresence>
        {open ? (
          <>
            <motion.button
              type="button"
              className="subsystems-drawer-scrim birth-diagnostics-backdrop"
              aria-label="Close diagnostics"
              initial={reducedMotion ? false : { opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setOpen(false)}
            />
            <motion.aside
              id="birth-diagnostics-panel"
              data-mode="SIM"
              className="birth-diagnostics-panel subsystems-drawer-airlock lumina-glass lumina-glass--overlay"
              initial={reducedMotion ? false : { opacity: 0, x: 24 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 24 }}
              transition={{ duration: 0.28 }}
            >
              <div className="mb-3 flex items-center justify-between gap-2">
                <p className="font-mono text-[10px] tracking-[0.16em] text-cyan-200/80 uppercase">
                  Birth diagnostics
                </p>
                <button
                  type="button"
                  className="rounded p-1 text-muted-foreground hover:text-foreground"
                  onClick={() => setOpen(false)}
                  aria-label="Close"
                >
                  <X className="size-4" />
                </button>
              </div>
              <div className="mb-3 flex flex-wrap gap-2">
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
            </motion.aside>
          </>
        ) : null}
      </AnimatePresence>
    </div>
  );
}
