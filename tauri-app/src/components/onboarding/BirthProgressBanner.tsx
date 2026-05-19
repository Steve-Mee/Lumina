import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";

import { Button } from "@/components/ui/button";
import { fetchBirthStatus } from "@/lib/setupClient";
import { useOnboardingStore } from "@/store/onboardingStore";

interface BirthProgress {
  status: string;
  message?: string;
  progress?: {
    progress_pct?: number;
    trades_done?: number;
    target_trades?: number;
    stage?: string;
  };
}

export function BirthProgressBanner() {
  const [birth, setBirth] = useState<BirthProgress | null>(null);
  const setPhase = useOnboardingStore((s) => s.setPhase);

  useEffect(() => {
    let active = true;
    const poll = async () => {
      try {
        const payload = (await fetchBirthStatus()) as unknown as BirthProgress;
        if (active) setBirth(payload);
        if (payload.status === "completed" || payload.status === "idle") {
          if (payload.status === "completed") return;
        }
      } catch {
        /* backend may be down briefly */
      }
    };
    void poll();
    const timer = setInterval(() => void poll(), 2000);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, []);

  const show =
    birth &&
    (birth.status === "running" ||
      (birth.status === "completed" && (birth.progress?.progress_pct ?? 100) < 100));

  if (!show || birth?.status === "idle") return null;

  const pct = birth.progress?.progress_pct ?? 0;
  const stage = birth.progress?.stage ?? birth.status;

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0, height: 0 }}
        animate={{ opacity: 1, height: "auto" }}
        exit={{ opacity: 0, height: 0 }}
        className="relative z-20 border-b border-cyan-400/20 bg-cyan-950/40 px-4 py-2 backdrop-blur-sm"
      >
        <div className="mx-auto flex max-w-4xl flex-col gap-1">
          <div className="flex flex-wrap items-center justify-between gap-2 text-xs tracking-wider uppercase">
            <span className="text-cyan-300/90">Birth Phase — {stage}</span>
            <div className="flex items-center gap-2">
              <span className="text-muted-foreground">{pct.toFixed(0)}%</span>
              {birth.status === "running" ? (
                <Button
                  type="button"
                  size="xs"
                  variant="secondary"
                  onClick={() => setPhase("birth")}
                >
                  View birth progress
                </Button>
              ) : null}
            </div>
          </div>
          <div className="h-1 overflow-hidden rounded-full bg-white/10">
            <div
              className="h-full bg-gradient-to-r from-cyan-400 to-violet-500 transition-all duration-700"
              style={{ width: `${Math.min(100, pct)}%` }}
            />
          </div>
          {birth.message && (
            <p className="truncate text-[10px] text-muted-foreground">{birth.message}</p>
          )}
        </div>
      </motion.div>
    </AnimatePresence>
  );
}
