import { AnimatePresence, motion } from "framer-motion";
import type { ReactNode } from "react";

import { PanelLoader } from "@/components/cockpit/PanelLoader";
import { useModeMotion } from "@/hooks/useModeMotion";
import { usePrefersReducedMotion } from "@/hooks/usePrefersReducedMotion";
import { fadeIn, transitionOrNone } from "@/lib/motionPresets";
import { modePanelClass, modeTitleClass } from "@/lib/modePresentation";
import { selectCurrentMode, useCoreStore } from "@/store/coreStore";
import { cn } from "@/lib/utils";

interface CorePanelSlotProps {
  title: string;
  subtitle?: string;
  children?: ReactNode;
  className?: string;
  loading?: boolean;
  loadingLabel?: string;
  immersive?: boolean;
}

export function CorePanelSlot({
  title,
  subtitle,
  children,
  className,
  loading = false,
  loadingLabel = "Syncing telemetry…",
  immersive = false,
}: CorePanelSlotProps) {
  const reducedMotion = usePrefersReducedMotion();
  const modeMotion = useModeMotion();
  const mode = useCoreStore(selectCurrentMode);

  return (
    <div
      data-mode={mode}
      className={cn(
        "lumina-glass lumina-glass--panel lumina-glass--interactive flex min-h-0 flex-1 flex-col rounded-lg py-0",
        modePanelClass(mode),
        className,
      )}
    >
      <div className="relative border-b border-white/5 px-4 py-3">
        <motion.div
          className="deck-panel-accent absolute inset-x-4 top-0 h-px origin-left"
          initial={reducedMotion ? { scaleX: 1 } : { scaleX: 0 }}
          animate={{ scaleX: 1 }}
          transition={transitionOrNone(reducedMotion, { ...modeMotion, delay: 0.1 })}
        />
        <h2
          className={cn(
            "deck-title mode-text-tier2",
            modeTitleClass(mode),
          )}
        >
          {title}
        </h2>
        {subtitle && !immersive ? (
          <p className="font-mono text-[11px] text-muted-foreground/80">{subtitle}</p>
        ) : null}
      </div>
      <div
        className={cn(
          "relative flex flex-1 items-stretch justify-stretch",
          immersive ? "p-0" : "p-2",
        )}
      >
        <AnimatePresence mode="wait" initial={false}>
          {loading ? (
            <motion.div
              key="loader"
              className="absolute inset-2 z-10 flex items-center justify-center rounded-lg lumina-glass"
              variants={fadeIn}
              initial={reducedMotion ? false : "hidden"}
              animate="visible"
              exit={reducedMotion ? undefined : "hidden"}
              transition={transitionOrNone(reducedMotion, modeMotion)}
            >
              <PanelLoader label={loadingLabel} className="min-h-0" />
            </motion.div>
          ) : null}
        </AnimatePresence>
        {children ?? (
          <p className="font-mono text-xs text-muted-foreground/60">Standby</p>
        )}
      </div>
    </div>
  );
}
