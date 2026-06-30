import { useEffect, useState } from "react";

import {
  GenesisMaturityLadder,
  type MaturationPhaseId,
} from "@/components/birth/GenesisMaturityLadder";
import { fetchMaturationProgress } from "@/lib/maturationClient";
import { cn } from "@/lib/utils";

interface MaturityProgressStripProps {
  className?: string;
}

export function MaturityProgressStrip({ className }: MaturityProgressStripProps) {
  const [phase, setPhase] = useState<MaturationPhaseId>("playground");
  const [eligible, setEligible] = useState(false);
  const [blockers, setBlockers] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void fetchMaturationProgress()
      .then((payload) => {
        if (cancelled) return;
        const raw = String(payload.current_phase || "playground") as MaturationPhaseId;
        setPhase(raw);
        setEligible(Boolean(payload.real_trading_eligible));
        setBlockers(Array.isArray(payload.real_trading_blockers) ? payload.real_trading_blockers : []);
        setError(null);
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Maturity status unavailable");
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div
      className={cn(
        "rounded-lg border border-border/40 bg-muted/10 px-3 py-2",
        className,
      )}
    >
      <div className="mb-1.5 flex items-center justify-between gap-2">
        <p className="font-mono text-[9px] tracking-[0.14em] text-muted-foreground uppercase">
          Lumina maturation
        </p>
        <span
          className={cn(
            "font-mono text-[9px] uppercase",
            eligible ? "text-emerald-300/90" : "text-amber-300/90",
          )}
        >
          {eligible ? "REAL eligible" : "REAL blocked"}
        </span>
      </div>
      <GenesisMaturityLadder activePhase={phase} />
      {!eligible && blockers.length > 0 ? (
        <ul className="mt-2 space-y-0.5 font-mono text-[9px] text-amber-200/80">
          {blockers.map((item) => (
            <li key={item}>· {item}</li>
          ))}
        </ul>
      ) : null}
      {!eligible ? (
        <p className="mt-1 font-mono text-[9px] text-muted-foreground/70">
          Apprenticeship details: Intelligence → Evolution → SIM Readiness
        </p>
      ) : null}
      {error ? (
        <p className="mt-1 font-mono text-[9px] text-muted-foreground/70">{error}</p>
      ) : null}
    </div>
  );
}
