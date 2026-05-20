import type { ReactNode } from "react";

import { ShieldAlert, Zap } from "lucide-react";

import { AnimatePresence, motion } from "framer-motion";



import { useAdaptiveIntelligenceContext } from "@/context/AdaptiveIntelligenceContext";

import { useModeMotion } from "@/hooks/useModeMotion";

import { usePrefersReducedMotion } from "@/hooks/usePrefersReducedMotion";

import { deckSyncNote } from "@/lib/deckStatusModel";

import { resolveVitality } from "@/lib/organismVitalityModel";

import { presenceDotClass } from "@/lib/pulseLanguage";

import { fadeIn, transitionOrNone } from "@/lib/motionPresets";

import {

  selectConnectionStatus,

  selectCurrentMode,

  selectFallbackMode,

  selectModeSyncStatus,

  useCoreStore,

  type TradingMode,

} from "@/store/coreStore";

import { cn } from "@/lib/utils";



interface PresenceRailProps {

  className?: string;

  engineAlive?: boolean;

  statusChip?: ReactNode;

  equityCompact?: string;

  hideSyncSecondary?: boolean;

}



const MODE_COPY: Record<TradingMode, { tagline: string; Icon: typeof Zap }> = {

  SIM: { tagline: "Hyper Evolution", Icon: Zap },

  REAL: { tagline: "Capital Protection", Icon: ShieldAlert },

};



export function PresenceRail({
  className,
  engineAlive = false,
  statusChip,
  equityCompact,
  hideSyncSecondary = false,
}: PresenceRailProps) {

  const mode = useCoreStore(selectCurrentMode);

  const modeSyncStatus = useCoreStore(selectModeSyncStatus);

  const modeSyncError = useCoreStore((s) => s.modeSyncError);

  const connectionStatus = useCoreStore(selectConnectionStatus);

  const fallbackMode = useCoreStore(selectFallbackMode);

  const { metrics } = useAdaptiveIntelligenceContext();

  const reducedMotion = usePrefersReducedMotion();

  const modeMotion = useModeMotion();



  const { tagline, Icon } = MODE_COPY[mode];

  const isSim = mode === "SIM";

  const syncPending = modeSyncStatus === "pending";

  const syncNote = deckSyncNote(modeSyncStatus, modeSyncError);



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

  const secondaryLabel = syncNote && hideSyncSecondary
    ? "—"
    : syncNote
    ? syncNote.replace(/^·\s*/, "")
    : equityCompact && vitality.tier !== "session" && (metrics?.velocity == null || metrics.velocity <= 0)
      ? equityCompact
      : metrics?.velocity != null && metrics.velocity > 0
        ? `${metrics.velocity.toFixed(1)} tpm`
        : vitality.tier === "dormant"
          ? vitality.transportLabel
          : "—";

  const secondaryKey = syncNote ? `sync-${modeSyncStatus}` : secondaryLabel;

  const dotActive = vitality.tier === "session" || vitality.tier === "engine";



  return (

    <div

      role="status"

      aria-live="polite"

      data-mode={mode}

      className={cn(

        "presence-rail flex h-8 shrink-0 items-center gap-3 border-b px-4 md:px-5",

        isSim ? "border-cyan-400/15 text-cyan-100" : "border-slate-500/15 text-slate-100/90",

        className,

      )}

    >

      <AnimatePresence mode="wait">

        <motion.div

          key={mode}

          initial={reducedMotion ? false : { opacity: 0, x: -4 }}

          animate={{ opacity: 1, x: 0 }}

          exit={reducedMotion ? undefined : { opacity: 0, x: 4 }}

          transition={transitionOrNone(reducedMotion, modeMotion)}

          className="flex min-w-0 shrink-0 items-center"

        >

          <Icon

            className={cn(

              "size-3 shrink-0",

              isSim ? "text-cyan-300" : "text-[#c9b896]",

              syncPending && !reducedMotion && "presence-rail__sync-pulse",

            )}

            title={tagline}

            aria-label={tagline}

          />

        </motion.div>

      </AnimatePresence>



      <div className="presence-rail__live flex min-w-0 flex-1 items-center gap-2 font-mono text-[10px]">

        <span

          className={cn(

            "presence-rail__live-dot relative size-2 shrink-0 rounded-full",

            dotActive

              ? cn(presenceDotClass(mode, Boolean(vitality.showEngineCompanion)), "lumina-glow-edge")

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



      <div className="flex shrink-0 items-center gap-2 font-mono text-[10px] tracking-[0.12em] uppercase">

        {statusChip ? <span className="hidden sm:inline">{statusChip}</span> : null}

        <span className="presence-rail__velocity">

          <AnimatePresence mode="wait" initial={false}>

            <motion.span

              key={secondaryKey}

              variants={fadeIn}

              initial={reducedMotion ? false : "hidden"}

              animate="visible"

              exit={reducedMotion ? undefined : "hidden"}

              transition={transitionOrNone(reducedMotion, modeMotion)}

              className={cn(!isSim && "text-slate-500/50")}

            >

              {secondaryLabel}

            </motion.span>

          </AnimatePresence>

        </span>

      </div>

    </div>

  );

}


