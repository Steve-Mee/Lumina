import { motion } from "framer-motion";
import { ShieldAlert } from "lucide-react";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { useModeMotion } from "@/hooks/useModeMotion";
import { usePrefersReducedMotion } from "@/hooks/usePrefersReducedMotion";
import { transitionOrNone } from "@/lib/motionPresets";
import {
  deckOverlayScrimClass,
  realOverlayBodyClass,
  realOverlayIconClass,
  realOverlayMetaClass,
  realOverlayPanelClass,
  realOverlayTitleClass,
} from "@/lib/modePresentation";
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
  const modeMotion = useModeMotion();
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
      transition={transitionOrNone(reducedMotion, modeMotion)}
      className={cn("real-safe-mode-overlay", deckOverlayScrimClass("safe"))}
    >
      <div className={cn("w-full max-w-lg rounded-xl p-6", realOverlayPanelClass())}>
        <div className="flex items-start gap-4">
          <ShieldAlert className={cn("mt-0.5 size-8 shrink-0", realOverlayIconClass())} aria-hidden />
          <div className="min-w-0">
            <h2 id="real-safe-mode-title" className={realOverlayTitleClass()}>
              Safe Mode — Backend Unreachable
            </h2>
            <p id="real-safe-mode-description" className={cn("mt-3", realOverlayBodyClass())}>
              REAL mode is active and the live backend connection has been lost for
              more than 15 seconds. Capital protection cannot be verified remotely.
              Trading controls are blocked until the WebSocket reconnects.
            </p>
          </div>
        </div>

        <dl className={cn("mt-5 grid gap-2 rounded-lg border border-slate-500/20 lumina-surface-muted px-3 py-2.5", realOverlayMetaClass())}>
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
              <dd className="truncate text-right text-slate-300/80">{lastError}</dd>
            </div>
          ) : null}
        </dl>

        <div className="mt-6 flex justify-end">
          <Button type="button" variant="command-primary" onClick={() => connectCoreLive()}>
            Retry connection
          </Button>
        </div>
      </div>
    </motion.div>
  );
}
