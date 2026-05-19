import { ShieldAlert, Zap } from "lucide-react";
import { AnimatePresence, motion } from "framer-motion";

import { usePrefersReducedMotion } from "@/hooks/usePrefersReducedMotion";
import { slideDown, springSoft, transitionOrNone } from "@/lib/motionPresets";
import {
  selectCurrentMode,
  useCoreStore,
  type TradingMode,
} from "@/store/coreStore";
import { cn } from "@/lib/utils";

interface ModeBannerProps {
  className?: string;
}

const BANNER_COPY: Record<
  TradingMode,
  { label: string; sublabel: string; Icon: typeof Zap }
> = {
  SIM: {
    label: "Hyper Evolution",
    sublabel: "Accelerated learning — simulation mode active",
    Icon: Zap,
  },
  REAL: {
    label: "Capital Protection Active",
    sublabel: "Conservative sizing and fail-closed safeguards enforced",
    Icon: ShieldAlert,
  },
};

export function ModeBanner({ className }: ModeBannerProps) {
  const mode = useCoreStore(selectCurrentMode);
  const reducedMotion = usePrefersReducedMotion();
  const { label, sublabel, Icon } = BANNER_COPY[mode];
  const isSim = mode === "SIM";

  return (
    <motion.div
      role="status"
      aria-live="polite"
      initial={reducedMotion ? false : "hidden"}
      animate="visible"
      variants={slideDown}
      transition={transitionOrNone(reducedMotion, springSoft)}
      className={cn(
        "mode-banner relative z-20 shrink-0 overflow-hidden border-b px-5 py-2 backdrop-blur-md",
        isSim
          ? "border-cyan-400/25 bg-gradient-to-r from-cyan-500/10 via-violet-500/10 to-fuchsia-500/10 text-cyan-100"
          : "border-amber-500/20 bg-slate-900/60 text-amber-100/90",
        className,
      )}
    >
      {isSim && !reducedMotion ? (
        <motion.div
          className="pointer-events-none absolute inset-0 bg-gradient-to-r from-transparent via-cyan-400/10 to-transparent"
          animate={{ x: ["-100%", "100%"] }}
          transition={{ duration: 4, repeat: Infinity, ease: "linear" }}
          aria-hidden
        />
      ) : null}

      <div className="relative flex items-center gap-3">
        <AnimatePresence mode="wait">
          <motion.div
            key={mode}
            initial={reducedMotion ? false : { opacity: 0, x: -6 }}
            animate={{ opacity: 1, x: 0 }}
            exit={reducedMotion ? undefined : { opacity: 0, x: 6 }}
            transition={{ duration: 0.2 }}
            className="flex items-center gap-3"
          >
            <Icon
              className={cn(
                "size-4 shrink-0",
                isSim ? "text-cyan-300" : "text-amber-400",
              )}
              aria-hidden
            />
            <div className="min-w-0 font-mono text-[11px] leading-relaxed">
              <p
                className={cn(
                  "tracking-[0.12em] uppercase",
                  isSim ? "text-cyan-200" : "text-amber-200",
                )}
              >
                {label}
              </p>
              <p
                className={cn(
                  "mt-0.5 text-[10px]",
                  isSim ? "text-cyan-100/70" : "text-amber-100/60",
                )}
              >
                {sublabel}
              </p>
            </div>
          </motion.div>
        </AnimatePresence>
      </div>
    </motion.div>
  );
}
