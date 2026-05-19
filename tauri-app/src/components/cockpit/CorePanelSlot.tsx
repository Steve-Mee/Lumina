import { AnimatePresence, motion } from "framer-motion";
import type { ReactNode } from "react";

import { PanelLoader } from "@/components/cockpit/PanelLoader";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { usePrefersReducedMotion } from "@/hooks/usePrefersReducedMotion";
import { fadeIn, springSoft, transitionOrNone } from "@/lib/motionPresets";
import { cn } from "@/lib/utils";

interface CorePanelSlotProps {
  title: string;
  subtitle: string;
  children?: ReactNode;
  className?: string;
  loading?: boolean;
  loadingLabel?: string;
}

export function CorePanelSlot({
  title,
  subtitle,
  children,
  className,
  loading = false,
  loadingLabel = "Syncing telemetry…",
}: CorePanelSlotProps) {
  const reducedMotion = usePrefersReducedMotion();

  return (
    <Card
      className={cn(
        "cockpit-panel ring-0 flex min-h-0 flex-1 flex-col py-0",
        className,
      )}
    >
      <CardHeader className="relative border-b border-white/5 px-4 py-3">
        <motion.div
          className="absolute inset-x-4 top-0 h-px origin-left bg-gradient-to-r from-cyan-400/60 to-violet-400/30"
          initial={reducedMotion ? { scaleX: 1 } : { scaleX: 0 }}
          animate={{ scaleX: 1 }}
          transition={transitionOrNone(reducedMotion, { ...springSoft, delay: 0.1 })}
        />
        <CardTitle className="font-mono text-xs tracking-[0.18em] text-cyan-200/90 uppercase">
          {title}
        </CardTitle>
        <CardDescription className="font-mono text-[11px] text-muted-foreground/80">
          {subtitle}
        </CardDescription>
      </CardHeader>
      <CardContent className="relative flex flex-1 items-stretch justify-stretch p-2">
        <AnimatePresence mode="wait" initial={false}>
          {loading ? (
            <motion.div
              key="loader"
              className="absolute inset-2 z-10 flex items-center justify-center rounded-lg bg-black/40 backdrop-blur-sm"
              variants={fadeIn}
              initial={reducedMotion ? false : "hidden"}
              animate="visible"
              exit={reducedMotion ? undefined : "hidden"}
              transition={{ duration: 0.2 }}
            >
              <PanelLoader label={loadingLabel} className="min-h-0" />
            </motion.div>
          ) : null}
        </AnimatePresence>
        {children ?? (
          <p className="font-mono text-xs text-muted-foreground/60">Standby</p>
        )}
      </CardContent>
    </Card>
  );
}
