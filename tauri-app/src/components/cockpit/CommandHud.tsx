import { useEffect, useState } from "react";
import { motion } from "framer-motion";

import { AnimatedMetric } from "@/components/cockpit/AnimatedMetric";
import { LaunchNinjaTraderButton } from "@/components/cockpit/LaunchNinjaTraderButton";
import { VisualSettingsDialog } from "@/components/cockpit/VisualSettingsDialog";
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

import { cn } from "@/lib/utils";
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

  const currentMode = useCoreStore(selectCurrentMode);

  const reportedMode = useCoreStore(selectReportedMode);

  const modeSyncStatus = useCoreStore(selectModeSyncStatus);

  const setOperatorMode = useCoreStore((state) => state.setOperatorMode);

  const liveMetrics = useCoreStore(selectLiveMetrics);

  const riskLevel = useCoreStore(selectRiskLevel);

  const evolutionState = useCoreStore(selectEvolutionState);

  const connectionStatus = useCoreStore(selectConnectionStatus);

  const fallbackMode = useCoreStore(selectFallbackMode);



  useEffect(() => {

    const timer = window.setInterval(() => {

      setClock(formatClock(new Date()));

    }, 1000);

    return () => window.clearInterval(timer);

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

  };



  const transportLabel = fallbackMode

    ? "Polling"

    : TRANSPORT_LABEL[connectionStatus];



  return (

    <>

      <header

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
          </div>



          <div className="command-hud-metrics flex gap-2 overflow-x-auto pb-0.5 lg:flex-1 lg:justify-center">

            <MetricPill label="Equity" value={formatEquity(liveMetrics.equity)} />

            <MetricPill label="Regime" value={liveMetrics.regime} accent="violet" />

            <MetricPill label="Risk" value={riskLevel} accent="amber" />

            <MetricPill

              label="Proposals"

              value={String(evolutionState.pendingCount)}

              accent="cyan"

            />

            <MetricPill label="Transport" value={transportLabel} accent="emerald" />

          </div>



          <div className="flex items-center justify-between gap-3 lg:justify-end">
            <VisualSettingsDialog />
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

    </>

  );

}

