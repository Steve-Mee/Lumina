import { motion } from "framer-motion";
import { ShieldAlert } from "lucide-react";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { usePrefersReducedMotion } from "@/hooks/usePrefersReducedMotion";
import { transitionOrNone } from "@/lib/motionPresets";
import { shouldShowSafeModeOverlay } from "@/lib/realSafeMode";
import { connectCoreLive } from "@/lib/websocket";
import {
  selectConnectionStatus,
  selectCurrentMode,
  selectFallbackMode,
  selectSafeModeActive,
  selectSafeModeSince,
  useCoreStore,
} from "@/store/coreStore";
import { cn } from "@/lib/utils";

function formatElapsed(since: string | null): string {
  if (!since) {
    return "—";
  }
  const elapsedMs = Math.max(0, Date.now() - Date.parse(since));
  const seconds = Math.floor(elapsedMs / 1000);
  if (seconds < 60) {
    return `${seconds}s`;
  }
  const minutes = Math.floor(seconds / 60);
  const remSeconds = seconds % 60;
  return `${minutes}m ${remSeconds}s`;
}

export function RealSafeModeOverlay() {
  const operatorMode = useCoreStore(selectCurrentMode);
  const safeModeActive = useCoreStore(selectSafeModeActive);
  const safeModeSince = useCoreStore(selectSafeModeSince);
  const connectionStatus = useCoreStore(selectConnectionStatus);
  const fallbackMode = useCoreStore(selectFallbackMode);
  const lastError = useCoreStore((state) => state.lastError);
  const reducedMotion = usePrefersReducedMotion();
  const [elapsed, setElapsed] = useState(() => formatElapsed(safeModeSince));

  const visible = shouldShowSafeModeOverlay(operatorMode, safeModeActive);

  useEffect(() => {
    if (!visible) {
      return;
    }

    setElapsed(formatElapsed(safeModeSince));
    const timer = window.setInterval(() => {
      setElapsed(formatElapsed(safeModeSince));
    }, 1000);

    return () => window.clearInterval(timer);
  }, [safeModeSince, visible]);

  if (!visible) {
    return null;
  }

  return (
    <motion.div
      role="alertdialog"
      aria-modal="true"
      aria-labelledby="real-safe-mode-title"
      aria-describedby="real-safe-mode-description"
      initial={reducedMotion ? false : { opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={transitionOrNone(reducedMotion, { duration: 0.25 })}
      className={cn(
        "real-safe-mode-overlay fixed inset-0 z-[100] flex items-center justify-center bg-black/85 p-6 backdrop-blur-md",
      )}
    >
      <div className="w-full max-w-lg rounded-xl border border-amber-500/40 bg-slate-950/95 p-6 shadow-[0_0_48px_oklch(0.7_0.18_45/25%)]">
        <div className="flex items-start gap-4">
          <ShieldAlert className="mt-0.5 size-8 shrink-0 text-amber-400" aria-hidden />
          <div className="min-w-0">
            <h2
              id="real-safe-mode-title"
              className="font-mono text-sm tracking-[0.14em] text-amber-200 uppercase"
            >
              Safe Mode — Backend Unreachable
            </h2>
            <p
              id="real-safe-mode-description"
              className="mt-3 text-sm leading-relaxed text-amber-100/85"
            >
              REAL mode is active and the live backend connection has been lost for
              more than 15 seconds. Capital protection cannot be verified remotely.
              Trading controls are blocked until the WebSocket reconnects.
            </p>
          </div>
        </div>

        <dl className="mt-5 grid gap-2 rounded-lg border border-amber-500/20 bg-black/30 px-3 py-2.5 font-mono text-[10px] text-amber-100/75">
          <div className="flex justify-between gap-3">
            <dt>Connection</dt>
            <dd className="uppercase">{connectionStatus}</dd>
          </div>
          <div className="flex justify-between gap-3">
            <dt>Fallback polling</dt>
            <dd>{fallbackMode ? "active" : "inactive"}</dd>
          </div>
          <div className="flex justify-between gap-3">
            <dt>Safe mode elapsed</dt>
            <dd>{elapsed}</dd>
          </div>
          {lastError ? (
            <div className="flex justify-between gap-3">
              <dt>Last error</dt>
              <dd className="truncate text-right text-amber-200/80">{lastError}</dd>
            </div>
          ) : null}
        </dl>

        <div className="mt-6 flex justify-end">
          <Button
            type="button"
            className="bg-amber-600/85 text-amber-50 hover:bg-amber-600"
            onClick={() => connectCoreLive()}
          >
            Retry connection
          </Button>
        </div>
      </div>
    </motion.div>
  );
}
