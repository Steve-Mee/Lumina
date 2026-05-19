import { useEffect, useState } from "react";
import { Keyboard } from "lucide-react";
import { motion } from "framer-motion";

import { AnimatedMetric } from "@/components/cockpit/AnimatedMetric";
import { LaunchNinjaTraderButton } from "@/components/cockpit/LaunchNinjaTraderButton";
import { TrainingMonitorTrigger } from "@/components/cockpit/TrainingMonitorTrigger";
import { SettingsDialog } from "@/components/cockpit/SettingsDialog";
import { IntelligenceTierBadgeLive } from "@/components/intelligence/IntelligenceTierBadge";
import { Button } from "@/components/ui/button";

import { Card, CardContent } from "@/components/ui/card";

import {

  Dialog,

  DialogContent,

  DialogDescription,

  DialogFooter,

  DialogHeader,

  DialogTitle,

} from "@/components/ui/dialog";

import { handleRuntimeError } from "@/lib/runtimeErrorToast";
import { cn } from "@/lib/utils";
import { formatUsd } from "@/lib/tradingPerformanceModel";
import {
  emergencyStop,
  fetchRuntimeStatus,
  flattenPositions,
  startEngine,
  stopAllActivities,
  stopEngine,
  type RuntimeStatus,
} from "@/lib/runtimeClient";
import { toast } from "sonner";
import { springSnappy } from "@/lib/motionPresets";

import {

  selectConnectionStatus,

  selectCurrentMode,

  selectEvolutionState,

  selectFallbackMode,

  selectLiveMetrics,

  selectModeSyncStatus,

  selectReportedMode,

  selectRiskLevel,

  useCoreStore,

  type ConnectionStatus,

  type TradingMode,

} from "@/store/coreStore";

import { useDeckPanelStore } from "@/store/deckPanelStore";
import { selectApiKeyConfigured, useApiKeyStore } from "@/store/apiKeyStore";
import { useBotConfigStore } from "@/store/botConfigStore";



interface CommandHudProps {

  className?: string;

}



const TRANSPORT_LABEL: Record<ConnectionStatus, string> = {

  connected: "Live",

  connecting: "Connecting",

  reconnecting: "Reconnecting",

  disconnected: "Offline",

};



function formatClock(date: Date): string {

  return date.toLocaleTimeString(undefined, {

    hour: "2-digit",

    minute: "2-digit",

    second: "2-digit",

    hour12: false,

  });

}



function formatEquity(equity: number | null): string {

  if (equity === null) {

    return "—";

  }

  return equity.toLocaleString(undefined, {

    maximumFractionDigits: 0,

  });

}



function MetricPill({

  label,

  value,

  accent,

}: {

  label: string;

  value: string;

  accent?: "cyan" | "amber" | "emerald" | "violet";

}) {

  const accentClass =

    accent === "amber"

      ? "border-amber-400/25 text-amber-200"

      : accent === "emerald"

        ? "border-emerald-400/25 text-emerald-200"

        : accent === "violet"

          ? "border-violet-400/25 text-violet-200"

          : "border-cyan-400/25 text-cyan-200";



  return (

    <Card

      size="sm"

      className={cn(

        "cockpit-panel min-w-[108px] shrink-0 ring-0 py-0",

        accentClass,

      )}

    >

      <CardContent className="px-3 py-2">

        <p className="text-[9px] tracking-[0.14em] text-muted-foreground uppercase">

          {label}

        </p>

        <AnimatedMetric value={value} />

      </CardContent>

    </Card>

  );

}



function ModeSwitch({

  mode,

  reportedMode,

  syncStatus,

  onSelect,

}: {

  mode: TradingMode;

  reportedMode: TradingMode | null;

  syncStatus: "idle" | "pending" | "error";

  onSelect: (mode: TradingMode) => void;

}) {

  const showMismatch =

    reportedMode !== null && reportedMode !== mode && syncStatus !== "pending";

  const showSyncError = syncStatus === "error";



  return (

    <div className="relative flex items-center gap-2">

      {(showMismatch || showSyncError) && (

        <span

          className={cn(

            "absolute -top-1 -right-1 size-2 rounded-full",

            showSyncError ? "bg-red-400" : "bg-amber-400",

          )}

          title={

            showSyncError

              ? "Mode sync failed — local override active"

              : "Backend reports different mode"

          }

          aria-label={

            showSyncError ? "Mode sync error" : "Mode mismatch with backend"

          }

        />

      )}

      <motion.div
        layout
        className={cn(
          "flex rounded-lg border p-0.5 shadow-lg",
          mode === "SIM"
            ? "border-cyan-400/30 bg-cyan-950/40 shadow-[0_0_20px_oklch(0.75_0.15_195/15%)]"
            : "border-amber-400/30 bg-amber-950/30 shadow-[0_0_16px_oklch(0.7_0.18_45/12%)]",
        )}
        transition={springSnappy}
        role="group"
        aria-label="Trading mode"
      >

        {(["SIM", "REAL"] as const).map((option) => {

          const active = mode === option;

          return (

            <Button

              key={option}

              type="button"

              size="sm"

              variant="ghost"

              aria-pressed={active}

              onClick={() => onSelect(option)}

              className={cn(

                "h-9 min-w-[64px] font-mono text-[11px] tracking-[0.18em] uppercase transition-all",

                active && option === "SIM" &&

                  "bg-cyan-500/20 text-cyan-200 shadow-[0_0_14px_oklch(0.75_0.15_195/25%)] ring-1 ring-cyan-400/40",

                active && option === "REAL" &&

                  "bg-amber-500/20 text-amber-200 shadow-[0_0_12px_oklch(0.7_0.18_45/20%)] ring-1 ring-amber-400/35",

                !active && "text-muted-foreground/70 hover:text-foreground",

              )}

            >

              {option}

            </Button>

          );

        })}

      </motion.div>

    </div>

  );

}



export function CommandHud({ className }: CommandHudProps) {

  const [clock, setClock] = useState(() => formatClock(new Date()));

  const [realConfirmOpen, setRealConfirmOpen] = useState(false);
  const [safetyConfirmOpen, setSafetyConfirmOpen] = useState(false);
  const [realSafetyAck, setRealSafetyAck] = useState(false);
  const [runtime, setRuntime] = useState<RuntimeStatus | null>(null);

  const currentMode = useCoreStore(selectCurrentMode);

  const reportedMode = useCoreStore(selectReportedMode);

  const modeSyncStatus = useCoreStore(selectModeSyncStatus);

  const setOperatorMode = useCoreStore((state) => state.setOperatorMode);

  const liveMetrics = useCoreStore(selectLiveMetrics);

  const riskLevel = useCoreStore(selectRiskLevel);

  const evolutionState = useCoreStore(selectEvolutionState);

  const connectionStatus = useCoreStore(selectConnectionStatus);

  const fallbackMode = useCoreStore(selectFallbackMode);
  const apiKeyConfigured = useApiKeyStore(selectApiKeyConfigured);
  const botConfigDirty = useBotConfigStore((s) => s.isDirty);
  const saveBotConfig = useBotConfigStore((s) => s.save);



  useEffect(() => {

    const timer = window.setInterval(() => {

      setClock(formatClock(new Date()));

    }, 1000);

    return () => window.clearInterval(timer);

  }, []);

  useEffect(() => {
    if (!safetyConfirmOpen) {
      setRealSafetyAck(false);
    }
  }, [safetyConfirmOpen]);

  useEffect(() => {
    const refresh = () => {
      void fetchRuntimeStatus()
        .then(setRuntime)
        .catch(() => setRuntime(null));
    };
    refresh();
    const id = window.setInterval(refresh, 5000);
    return () => window.clearInterval(id);
  }, []);



  const handleModeSelect = (mode: TradingMode) => {

    if (mode === currentMode) {

      return;

    }

    if (mode === "REAL") {

      setRealConfirmOpen(true);

      return;

    }

    setOperatorMode(mode);

  };



  const confirmRealMode = () => {

    setOperatorMode("REAL");

    setRealConfirmOpen(false);

    if (!sessionStorage.getItem("lumina.realOpsHintShown")) {
      sessionStorage.setItem("lumina.realOpsHintShown", "1");
      toast.info("REAL Ops tab unlocked in Intelligence deck", {
        action: {
          label: "Open REAL Ops",
          onClick: () => useDeckPanelStore.getState().setActiveRightTab("realOps"),
        },
      });
    }

  };



  const transportLabel = fallbackMode

    ? "Polling"

    : TRANSPORT_LABEL[connectionStatus];



  return (

    <>

      <header

        data-tour="command-hud"

        className={cn(

          "command-hud relative z-10 shrink-0 border-b border-white/10 bg-black/25 px-4 py-3 backdrop-blur-md md:px-5",

          className,

        )}

      >

        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">

          <div className="flex flex-col gap-2 lg:flex-row lg:items-center lg:gap-3">
            <div className="flex items-center justify-between gap-3 lg:justify-start">
              <div className="flex items-center gap-3">
                <div className="size-2 rounded-full bg-cyan-400 shadow-[0_0_10px_var(--cockpit-glow-primary)]" />
                <div>
                  <p className="text-sm font-medium tracking-wide text-foreground">
                    LUMINA Neural Command Deck
                  </p>
                  <p className="font-mono text-[10px] tracking-[0.22em] text-muted-foreground uppercase">
                    The Core
                  </p>
                </div>
              </div>
              <time
                className="font-mono text-xs tabular-nums text-cyan-200/80 lg:hidden"
                dateTime={clock}
              >
                {clock}
              </time>
            </div>
            <LaunchNinjaTraderButton className="w-full lg:w-auto" />
            <div className="flex flex-wrap items-center gap-1.5">
              <Button
                type="button"
                size="xs"
                variant={runtime?.alive ? "secondary" : "default"}
                disabled={!runtime?.alive && !apiKeyConfigured}
                title={
                  !apiKeyConfigured && !runtime?.alive
                    ? "Configure admin API key in Settings to start the engine"
                    : undefined
                }
                onClick={() =>
                  void (runtime?.alive
                    ? stopEngine()
                        .then((r) => {
                          toast.success(r.message);
                          setRuntime({ ...runtime!, alive: false, message: r.message });
                        })
                        .catch(handleRuntimeError)
                    : startEngine()
                        .then((r) => {
                          toast.success(r.message);
                          void fetchRuntimeStatus().then(setRuntime);
                        })
                        .catch(handleRuntimeError))
                }
              >
                {runtime?.alive ? "Stop Engine" : "Start Engine"}
              </Button>
              {!runtime?.alive && apiKeyConfigured ? (
                <Button
                  type="button"
                  size="xs"
                  variant="outline"
                  title="Save bot config to config.yaml then start the engine"
                  onClick={() =>
                    void (async () => {
                      if (botConfigDirty()) {
                        const ok = await saveBotConfig();
                        if (!ok) {
                          toast.error("Save bot config before starting engine");
                          return;
                        }
                        toast.success("Bot configuration saved");
                      }
                      return startEngine()
                        .then((r) => {
                          toast.success(r.message);
                          void fetchRuntimeStatus().then(setRuntime);
                        })
                        .catch(handleRuntimeError);
                    })()
                  }
                >
                  Save & Start
                </Button>
              ) : null}
              <Button
                type="button"
                size="xs"
                variant="ghost"
                className="text-amber-200/90"
                onClick={() => setSafetyConfirmOpen(true)}
              >
                Safety
              </Button>
            </div>
          </div>



          <div className="command-hud-metrics flex gap-2 overflow-x-auto pb-0.5 lg:flex-1 lg:justify-center">

            <MetricPill label="Equity" value={formatEquity(liveMetrics.equity)} />

            <MetricPill
              label="Daily P&L"
              value={formatUsd(liveMetrics.dailyPnlUsd)}
              accent={liveMetrics.dailyPnlUsd != null && liveMetrics.dailyPnlUsd >= 0 ? "emerald" : "amber"}
            />

            <MetricPill label="Regime" value={liveMetrics.regime} accent="violet" />

            <MetricPill label="Risk" value={riskLevel} accent="amber" />

            <MetricPill

              label="Proposals"

              value={String(evolutionState.pendingCount)}

              accent="cyan"

            />

            <MetricPill label="Transport" value={transportLabel} accent="emerald" />

            <IntelligenceTierBadgeLive className="shrink-0" compact />

          </div>



          <div className="flex items-center justify-between gap-3 lg:justify-end">
            <TrainingMonitorTrigger />
            <div className="group relative hidden md:block">
              <Button
                type="button"
                size="sm"
                variant="ghost"
                className="h-9 w-9 p-0 text-muted-foreground hover:text-cyan-200"
                aria-label="Keyboard shortcuts"
              >
                <Keyboard className="size-4" />
              </Button>
              <div className="pointer-events-none absolute right-0 top-full z-50 mt-1 w-48 rounded-md border border-white/10 bg-black/90 p-2 opacity-0 shadow-lg transition-opacity group-hover:opacity-100 group-focus-within:opacity-100">
                <p className="font-mono text-[9px] tracking-wide text-cyan-300/80 uppercase">
                  Shortcuts
                </p>
                <ul className="mt-1 space-y-0.5 font-mono text-[10px] text-muted-foreground">
                  <li>Ctrl+E — Evolve</li>
                  <li>Ctrl+P — Pause</li>
                  <li>Ctrl+A — Approve last</li>
                </ul>
              </div>
            </div>
            <SettingsDialog />
            <ModeSwitch

              mode={currentMode}

              reportedMode={reportedMode}

              syncStatus={modeSyncStatus}

              onSelect={handleModeSelect}

            />

            <time

              className="hidden font-mono text-xs tabular-nums text-cyan-200/80 lg:block"

              dateTime={clock}

            >

              {clock}

            </time>

          </div>

        </div>

      </header>



      <Dialog open={realConfirmOpen} onOpenChange={setRealConfirmOpen}>

        <DialogContent>

          <DialogHeader>

            <DialogTitle className="text-amber-200">

              Enable REAL Mode?

            </DialogTitle>

            <DialogDescription className="leading-relaxed">

              REAL mode engages live capital protection: conservative sizing,

              fail-closed safeguards, and EOD flatten rules. Confirm only after

              safety gate checks are green and you accept capital risk.

            </DialogDescription>

          </DialogHeader>

          <DialogFooter>

            <Button

              type="button"

              variant="ghost"

              onClick={() => setRealConfirmOpen(false)}

            >

              Cancel

            </Button>

            <Button

              type="button"

              className="bg-amber-600/80 text-amber-50 hover:bg-amber-600"

              onClick={confirmRealMode}

            >

              Confirm REAL

            </Button>

          </DialogFooter>

        </DialogContent>

      </Dialog>

      <Dialog open={safetyConfirmOpen} onOpenChange={setSafetyConfirmOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="text-red-200">Safety actions</DialogTitle>
            <DialogDescription>
              Flatten closes open positions. Emergency stop cancels orders and flattens all.
              {currentMode === "REAL" ? " These actions affect live capital." : null}
            </DialogDescription>
          </DialogHeader>
          {currentMode === "REAL" ? (
            <label className="flex items-start gap-2 text-xs text-amber-200/90">
              <input
                type="checkbox"
                className="mt-0.5"
                checked={realSafetyAck}
                onChange={(e) => setRealSafetyAck(e.target.checked)}
              />
              I understand this affects live capital
            </label>
          ) : null}
          <DialogFooter className="flex-wrap gap-2">
            <Button type="button" variant="ghost" onClick={() => setSafetyConfirmOpen(false)}>
              Cancel
            </Button>
            <Button
              type="button"
              variant="secondary"
              onClick={() => {
                void flattenPositions()
                  .then(() => toast.success("Positions flattened"))
                  .catch(handleRuntimeError);
                setSafetyConfirmOpen(false);
              }}
            >
              Flatten
            </Button>
            <Button
              type="button"
              className="bg-red-700/80 text-red-50"
              disabled={currentMode === "REAL" && !realSafetyAck}
              onClick={() => {
                void emergencyStop()
                  .then(() => toast.success("Emergency stop executed"))
                  .catch(handleRuntimeError);
                setSafetyConfirmOpen(false);
              }}
            >
              Emergency Stop
            </Button>
            <Button
              type="button"
              className="bg-red-900/80 text-red-50"
              disabled={currentMode === "REAL" && !realSafetyAck}
              onClick={() => {
                void stopAllActivities()
                  .then((r) => toast.success(r.message))
                  .catch(handleRuntimeError);
                setSafetyConfirmOpen(false);
              }}
            >
              Stop All
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

    </>

  );

}

