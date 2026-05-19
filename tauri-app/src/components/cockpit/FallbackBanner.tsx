import { AlertTriangle } from "lucide-react";
import { AnimatePresence, motion } from "framer-motion";

import { usePrefersReducedMotion } from "@/hooks/usePrefersReducedMotion";
import { slideDown, springSoft, transitionOrNone } from "@/lib/motionPresets";
import { selectFallbackMode, useCoreStore } from "@/store/coreStore";
import { cn } from "@/lib/utils";

interface FallbackBannerProps {
  className?: string;
}

export function FallbackBanner({ className }: FallbackBannerProps) {
  const fallbackMode = useCoreStore(selectFallbackMode);
  const lastError = useCoreStore((state) => state.lastError);
  const reducedMotion = usePrefersReducedMotion();

  return (
    <AnimatePresence initial={false}>
      {fallbackMode ? (
        <motion.div
          key="fallback-banner"
          role="alert"
          initial={reducedMotion ? false : "hidden"}
          animate="visible"
          exit="exit"
          variants={slideDown}
          transition={transitionOrNone(reducedMotion, springSoft)}
          className={cn(
            "relative z-20 flex items-start gap-3 overflow-hidden border-b border-amber-500/30 bg-amber-500/10 px-5 py-2.5 text-amber-100 backdrop-blur-md",
            className,
          )}
        >
          <AlertTriangle className="mt-0.5 size-4 shrink-0 text-amber-400" aria-hidden />
          <div className="min-w-0 font-mono text-[11px] leading-relaxed">
            <p className="tracking-[0.08em] uppercase text-amber-200">
              Live telemetry degraded — polling fallback active (WebSocket unavailable). Reconnecting…
            </p>
            {lastError ? (
              <p className="mt-1 truncate text-[10px] text-amber-100/70">{lastError}</p>
            ) : null}
          </div>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}
