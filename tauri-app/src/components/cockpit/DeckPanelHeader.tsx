import type { ReactNode } from "react";
import { motion } from "framer-motion";

import { useModeMotion } from "@/hooks/useModeMotion";
import { usePrefersReducedMotion } from "@/hooks/usePrefersReducedMotion";
import { transitionOrNone } from "@/lib/motionPresets";
import { modeTitleClass } from "@/lib/modePresentation";
import { selectCurrentMode, useCoreStore } from "@/store/coreStore";
import { cn } from "@/lib/utils";

interface DeckPanelHeaderProps {
  title: string;
  subtitle?: string;
  actions?: ReactNode;
  annex?: boolean;
  className?: string;
}

export function DeckPanelHeader({
  title,
  subtitle,
  actions,
  annex = false,
  className,
}: DeckPanelHeaderProps) {
  const reducedMotion = usePrefersReducedMotion();
  const modeMotion = useModeMotion();
  const mode = useCoreStore(selectCurrentMode);

  return (
    <div className={cn("relative border-b border-white/5 px-4 py-3", annex && "deck-header--annex", className)}>
      <motion.div
        className="deck-panel-accent absolute inset-x-4 top-0 h-px origin-left"
        initial={reducedMotion ? { scaleX: 1 } : { scaleX: 0 }}
        animate={{ scaleX: 1 }}
        transition={transitionOrNone(reducedMotion, { ...modeMotion, delay: 0.1 })}
      />
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2
            className={cn(
              "deck-header-title deck-title mode-text-tier2",
              annex ? "text-muted-foreground/80" : modeTitleClass(mode),
            )}
          >
            {title}
          </h2>
          {subtitle ? <p className="deck-subtitle">{subtitle}</p> : null}
        </div>
        {actions ? <div className="flex flex-wrap items-center gap-1">{actions}</div> : null}
      </div>
    </div>
  );
}
