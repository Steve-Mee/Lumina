import { motion } from "framer-motion";

import { Button } from "@/components/ui/button";
import { useModeMotion } from "@/hooks/useModeMotion";
import {
  modeSwitchShellClass,
  modeSwitchActivePillClass,
  modeSwitchActivePillMotionClass,
  modeSwitchTooltip,
} from "@/lib/modePresentation";
import { springLuxury } from "@/lib/motionPresets";
import { cn } from "@/lib/utils";
import type { TradingMode } from "@/store/coreStore";

export interface ModeSwitchProps {
  mode: TradingMode;
  reportedMode: TradingMode | null;
  syncStatus: "idle" | "pending" | "error";
  onSelect: (mode: TradingMode) => void;
  realEligible: boolean;
}

export function ModeSwitch({
  mode,
  reportedMode,
  syncStatus,
  onSelect,
  realEligible,
}: ModeSwitchProps) {
  const modeMotion = useModeMotion();
  const pillMotion = mode === "REAL" ? springLuxury : modeMotion;
  const showSyncDot = syncStatus === "pending" || syncStatus === "error";
  const showMismatch =
    reportedMode !== null && reportedMode !== mode && syncStatus !== "pending";

  return (
    <div className="relative flex flex-col items-end gap-0.5">
      {(showMismatch || showSyncDot) && (
        <span
          className={cn(
            "absolute -top-1 -right-1 size-2 rounded-full",
            syncStatus === "error" ? "bg-red-400" : "bg-[#c9b896]",
          )}
          title={
            syncStatus === "error"
              ? "Mode sync failed — local override active"
              : syncStatus === "pending"
                ? "Mode sync in progress"
                : "Backend reports different mode"
          }
          aria-label={
            syncStatus === "error"
              ? "Mode sync error"
              : syncStatus === "pending"
                ? "Mode syncing"
                : "Mode mismatch with backend"
          }
        />
      )}
      <motion.div
        layout
        className={cn(
          "relative flex rounded-lg border p-0.5 lumina-glow-edge",
          modeSwitchShellClass(mode),
        )}
        transition={modeMotion}
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
              variant="command-ghost"
              aria-pressed={active}
              title={modeSwitchTooltip(option)}
              onClick={() => {
                if (option === "REAL" && !realEligible) {
                  return;
                }
                onSelect(option);
              }}
              disabled={option === "REAL" && !realEligible}
              className={cn(
                "relative h-9 min-w-[64px] font-mono text-[11px] tracking-[0.18em] uppercase transition-colors",
                modeSwitchActivePillClass(option, active),
                !active && option === "REAL" && "text-slate-500/60 hover:text-slate-300/80",
                !active && option === "SIM" && "text-muted-foreground/70 hover:text-foreground",
              )}
            >
              {active ? (
                <motion.span
                  layoutId="mode-pill"
                  className={cn(
                    "absolute inset-0 rounded-md",
                    modeSwitchActivePillMotionClass(option),
                  )}
                  transition={pillMotion}
                />
              ) : null}
              <span className="relative z-[1]">{option}</span>
            </Button>
          );
        })}
      </motion.div>
      <span className="font-mono text-[9px] tracking-[0.14em] text-muted-foreground/70 uppercase">
        {modeSwitchTooltip(mode)}
      </span>
    </div>
  );
}