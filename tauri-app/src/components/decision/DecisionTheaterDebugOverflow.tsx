import { useEffect, useRef, useState } from "react";
import { ChevronDown } from "lucide-react";
import { AnimatePresence, motion } from "framer-motion";

import { useModeMotion } from "@/hooks/useModeMotion";
import { usePrefersReducedMotion } from "@/hooks/usePrefersReducedMotion";
import { hasDebugPayload } from "@/lib/decisionTheaterLayout";
import { menuPopWith, transitionOrNone } from "@/lib/motionPresets";
import type { LiveTradingSnapshot } from "@/lib/liveTradingTypes";
import { cn } from "@/lib/utils";

interface DecisionTheaterDebugOverflowProps {
  trading: LiveTradingSnapshot | null;
  className?: string;
}

export function DecisionTheaterDebugOverflow({
  trading,
  className,
}: DecisionTheaterDebugOverflowProps) {
  const reducedMotion = usePrefersReducedMotion();
  const modeMotion = useModeMotion();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  const visible = hasDebugPayload(trading);

  useEffect(() => {
    if (!open) {
      return;
    }
    const onPointerDown = (event: MouseEvent) => {
      if (ref.current && !ref.current.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", onPointerDown);
    return () => document.removeEventListener("mousedown", onPointerDown);
  }, [open]);

  if (!visible || !trading) {
    return null;
  }

  return (
    <div ref={ref} className={cn("relative shrink-0", className)}>
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="inline-flex items-center gap-1 font-mono text-[10px] tracking-wide text-muted-foreground uppercase transition-colors hover:text-cyan-200/90"
        aria-expanded={open}
      >
        Debug
        <ChevronDown className={cn("size-3 transition-transform", open && "rotate-180")} />
      </button>
      <AnimatePresence>
        {open ? (
          <motion.div
            key="theater-debug"
            className="absolute bottom-full right-0 z-30 mb-1 w-[min(420px,85vw)] rounded-md p-3 lumina-glass"
            variants={menuPopWith(modeMotion)}
            initial={reducedMotion ? false : "hidden"}
            animate="visible"
            exit={reducedMotion ? undefined : "exit"}
            transition={transitionOrNone(reducedMotion, modeMotion)}
          >
            {trading.current_dream ? (
              <div className="mb-3">
                <p className="mb-1 font-mono text-[9px] tracking-wide text-cyan-300/80 uppercase">
                  Current Dream
                </p>
                <pre className="max-h-40 overflow-auto whitespace-pre-wrap font-mono text-[10px] text-muted-foreground">
                  {JSON.stringify(trading.current_dream, null, 2)}
                </pre>
              </div>
            ) : null}
            {trading.runtime_state ? (
              <div>
                <p className="mb-1 font-mono text-[9px] tracking-wide text-cyan-300/80 uppercase">
                  Runtime State
                </p>
                <pre className="max-h-40 overflow-auto whitespace-pre-wrap font-mono text-[10px] text-muted-foreground">
                  {JSON.stringify(trading.runtime_state, null, 2)}
                </pre>
              </div>
            ) : null}
          </motion.div>
        ) : null}
      </AnimatePresence>
    </div>
  );
}
