
import { ShieldAlert, Zap } from "lucide-react";

import { AnimatePresence, motion } from "framer-motion";

import { useAdaptiveIntelligenceContext } from "@/context/AdaptiveIntelligenceContext";
import { useModeMotion } from "@/hooks/useModeMotion";
import { usePrefersReducedMotion } from "@/hooks/usePrefersReducedMotion";
import { resolveVitality } from "@/lib/organismVitalityModel";
import { presenceDotClass } from "@/lib/pulseLanguage";
import { fadeIn, transitionOrNone } from "@/lib/motionPresets";
import {
  selectConnectionStatus,
  selectCurrentMode,
  selectFallbackMode,
  useCoreStore,
} from "@/store/coreStore";
import { cn } from "@/lib/utils";

interface PresenceRailProps {
  className?: string;
  engineAlive?: boolean;
  heroReadout?: { label: string; value: string };
  equityCompact?: string;
}

const MODE_COPY = {
  SIM: { tagline: "Hyper Evolution", Icon: Zap },
  REAL: { tagline: "Capital Protection", Icon: ShieldAlert },
} as const;

export function PresenceRail({
  className,
  engineAlive = false,
  heroReadout,
  equityCompact,
}: PresenceRailProps) {
  const mode = useCoreStore(selectCurrentMode);
  const connectionStatus = useCoreStore(selectConnectionStatus);
  const fallbackMode = useCoreStore(selectFallbackMode);
  const { metrics } = useAdaptiveIntelligenceContext();
  const reducedMotion = usePrefersReducedMotion();
  const modeMotion = useModeMotion();

  const { tagline, Icon } = MODE_COPY[mode];

  const phaseLabel =
    metrics?.phase || metrics?.first_boot_stage || metrics?.session_kind || "idle";

  const vitality = resolveVitality({
    connectionStatus,
    fallbackMode,
    sessionActive: Boolean(metrics?.session_active),
    activityStale: Boolean(metrics?.activity_stale),
    engineAlive,
    mode,
    phaseLabel,
  });

  const primaryKey = `${vitality.tier}-${vitality.primaryLabel}`;
  const secondaryLabel =
    heroReadout
      ? `${heroReadout.label} ${heroReadout.value}`
      : equityCompact && vitality.tier !== "session" && (metrics?.velocity == null || metrics.velocity <= 0)
        ? equityCompact
        : metrics?.velocity != null && metrics.velocity > 0
          ? `${metrics.velocity.toFixed(1)} tpm`
          : vitality.tier === "dormant"
            ? vitality.transportLabel
            : "—";

  const secondaryKey = secondaryLabel;
  const dotActive = vitality.tier === "session" || vitality.tier === "engine";

  return (
    <div
      role="status"
      aria-live="polite"
      data-mode={mode}
      className={cn("presence-rail flex h-8 shrink-0 items-center gap-3 border-b px-4 md:px-5", className)}
    >
      <AnimatePresence mode="wait">
        <motion.div
          key={mode}
          initial={reducedMotion ? false : { opacity: 0, x: -4 }}
          animate={{ opacity: 1, x: 0 }}
          exit={reducedMotion ? undefined : { opacity: 0, x: 4 }}
          transition={transitionOrNone(reducedMotion, modeMotion)}
          className="flex min-w-0 shrink-0 items-center gap-1.5"
        >
          <Icon
            className="presence-rail__mode-icon size-3 shrink-0"
aria-label={tagline}
          />
        </motion.div>
      </AnimatePresence>

      <div className="presence-rail__live flex min-w-0 flex-1 items-center gap-2 font-mono text-[10px]">
        <span
          className={cn(
            "presence-rail__live-dot relative size-2 shrink-0 rounded-full",
            dotActive
              ? presenceDotClass(mode, Boolean(vitality.showEngineCompanion))
              : vitality.tier === "degraded"
                ? "bg-amber-400/90"
                : "bg-slate-500",
          )}
          title={vitality.engineGlyph ?? undefined}
        />

        <AnimatePresence mode="wait" initial={false}>
          <motion.span
            key={primaryKey}
            className="truncate tracking-wide text-foreground/90 uppercase"
            variants={fadeIn}
            initial={reducedMotion ? false : "hidden"}
            animate="visible"
            exit={reducedMotion ? undefined : "hidden"}
            transition={transitionOrNone(reducedMotion, modeMotion)}
          >
            {vitality.primaryLabel}
          </motion.span>
        </AnimatePresence>
      </div>

      <div className="presence-rail__velocity flex shrink-0 items-center gap-2 font-mono text-[10px] tracking-[0.12em] uppercase">
        <AnimatePresence mode="wait" initial={false}>
          <motion.span
            key={secondaryKey}
            variants={fadeIn}
            initial={reducedMotion ? false : "hidden"}
            animate="visible"
            exit={reducedMotion ? undefined : "hidden"}
            transition={transitionOrNone(reducedMotion, modeMotion)}
          >
            {secondaryLabel}
          </motion.span>
        </AnimatePresence>
      </div>
    </div>
  );
}
