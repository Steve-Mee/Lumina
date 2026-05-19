import { AnimatePresence, motion } from "framer-motion";

import { Separator } from "@/components/ui/separator";
import { usePrefersReducedMotion } from "@/hooks/usePrefersReducedMotion";
import { fadeIn, springSnappy, transitionOrNone } from "@/lib/motionPresets";
import {
  selectConnectionStatus,
  selectFallbackMode,
  selectLiveMetrics,
  useCoreStore,
  type ConnectionStatus,
} from "@/store/coreStore";
import { cn } from "@/lib/utils";

interface StatusBarProps {
  className?: string;
}

const STATUS_LABEL: Record<ConnectionStatus, string> = {
  connected: "Live",
  connecting: "Connecting",
  reconnecting: "Reconnecting",
  disconnected: "Offline",
};

const STATUS_DOT: Record<ConnectionStatus, string> = {
  connected: "bg-emerald-400/90 shadow-[0_0_8px_oklch(0.72_0.17_155/50%)]",
  connecting: "bg-amber-400/90 shadow-[0_0_8px_oklch(0.78_0.15_85/50%)] animate-pulse",
  reconnecting: "bg-amber-400/90 shadow-[0_0_8px_oklch(0.78_0.15_85/50%)] animate-pulse",
  disconnected: "bg-red-400/80 shadow-[0_0_8px_oklch(0.65_0.2_25/50%)]",
};

export function StatusBar({ className }: StatusBarProps) {
  const status = useCoreStore(selectConnectionStatus);
  const fallbackMode = useCoreStore(selectFallbackMode);
  const liveMetrics = useCoreStore(selectLiveMetrics);
  const reducedMotion = usePrefersReducedMotion();

  const transportKey = fallbackMode ? "polling" : status;
  const transportLabel = fallbackMode ? "Polling" : STATUS_LABEL[status];
  const transportDot = fallbackMode
    ? "bg-amber-400/90 shadow-[0_0_8px_oklch(0.78_0.15_85/50%)] animate-pulse"
    : STATUS_DOT[status];

  const engineLabel =
    status === "connected" || fallbackMode
      ? `Engine: ${liveMetrics.regime}`
      : "Engine: standby";

  return (
    <footer
      className={cn(
        "relative z-10 flex h-10 shrink-0 items-center gap-4 border-t border-white/10 bg-black/30 px-5 font-mono text-[11px] text-muted-foreground backdrop-blur-md",
        className,
      )}
    >
      <div className="flex items-center gap-2">
        <span className={cn("size-1.5 rounded-full transition-colors duration-300", transportDot)} />
        <AnimatePresence mode="wait" initial={false}>
          <motion.span
            key={transportKey}
            className="tracking-[0.12em] uppercase"
            variants={fadeIn}
            initial={reducedMotion ? false : "hidden"}
            animate="visible"
            exit={reducedMotion ? undefined : "hidden"}
            transition={transitionOrNone(reducedMotion, springSnappy)}
          >
            {transportLabel}
          </motion.span>
        </AnimatePresence>
      </div>

      <Separator orientation="vertical" className="h-4 bg-white/10" />

      <AnimatePresence mode="wait" initial={false}>
        <motion.span
          key={engineLabel}
          variants={fadeIn}
          initial={reducedMotion ? false : "hidden"}
          animate="visible"
          exit={reducedMotion ? undefined : "hidden"}
          transition={transitionOrNone(reducedMotion, { duration: 0.2 })}
        >
          {engineLabel}
        </motion.span>
      </AnimatePresence>

      <Separator orientation="vertical" className="h-4 bg-white/10" />

      <span>v0.1.0</span>

      <div className="ml-auto flex items-center gap-2 text-cyan-200/60">
        <span className="tracking-[0.14em] uppercase">Tauri Shell</span>
      </div>
    </footer>
  );
}
