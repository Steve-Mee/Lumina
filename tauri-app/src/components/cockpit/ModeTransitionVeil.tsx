import { useEffect } from "react";
import { AnimatePresence, motion } from "framer-motion";

import { usePrefersReducedMotion } from "@/hooks/usePrefersReducedMotion";
import type { TradingMode } from "@/store/coreStore";
import { cn } from "@/lib/utils";

interface ModeTransitionVeilProps {
  active: boolean;
  targetMode: TradingMode | null;
  onComplete: () => void;
  /** CSS scope for shell animation; defaults to `.cockpit-shell` */
  scopeSelector?: string;
  /** Override animation duration in seconds */
  durationSec?: number;
}

export function ModeTransitionVeil({
  active,
  targetMode,
  onComplete,
  scopeSelector = ".cockpit-shell",
  durationSec,
}: ModeTransitionVeilProps) {
  const reducedMotion = usePrefersReducedMotion();
  const isReal = targetMode === "REAL";
  const duration = durationSec ?? (isReal ? 1 : 0.8);

  useEffect(() => {
    if (reducedMotion && active) {
      const id = window.setTimeout(onComplete, 150);
      return () => window.clearTimeout(id);
    }
    return undefined;
  }, [reducedMotion, active, onComplete]);

  useEffect(() => {
    const shell = document.querySelector(scopeSelector);
    if (!shell) {
      return;
    }
    if (active && targetMode) {
      shell.classList.add("mode-transition-active");
      shell.setAttribute("data-transition-target", targetMode);
      if (durationSec != null) {
        shell.style.setProperty("--mode-transition-duration", `${durationSec}s`);
      }
    } else {
      shell.classList.remove("mode-transition-active");
      shell.removeAttribute("data-transition-target");
      shell.style.removeProperty("--mode-transition-duration");
    }
    return () => {
      shell.classList.remove("mode-transition-active");
      shell.removeAttribute("data-transition-target");
      shell.style.removeProperty("--mode-transition-duration");
    };
  }, [active, targetMode, scopeSelector, durationSec]);

  return (
    <AnimatePresence onExitComplete={onComplete}>
      {active && targetMode ? (
        <motion.div
          key={targetMode}
          className={cn(
            "mode-transition-veil pointer-events-none fixed inset-0 z-[120]",
            targetMode === "REAL" ? "mode-transition-veil--real" : "mode-transition-veil--sim",
            reducedMotion && "mode-transition-veil--reduced",
          )}
          style={{ animationDuration: `${duration}s` }}
          initial={{ opacity: 0 }}
          animate={{ opacity: reducedMotion ? [0, 0.5, 0] : [0, 0.85, 0] }}
          exit={{ opacity: 0 }}
          transition={{ duration: reducedMotion ? 0.15 : duration, ease: "easeInOut" }}
          aria-hidden
        />
      ) : null}
    </AnimatePresence>
  );
}
