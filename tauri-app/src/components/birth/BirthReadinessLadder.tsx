import { useEffect, useState } from "react";

import type { BirthStatusPayload } from "@/lib/birthClient";
import { fetchMaturationProgress } from "@/lib/maturationClient";
import { cn } from "@/lib/utils";

interface BirthReadinessLadderProps {
  status: BirthStatusPayload | null;
  className?: string;
}

const REAL_MILESTONE_IDS = [
  "birth_certificate_issued",
  "evolution_proof_passed",
  "sim_real_guard_stable",
  "promotion_gate_passed",
] as const;

const REAL_MILESTONE_LABELS: Record<(typeof REAL_MILESTONE_IDS)[number], string> = {
  birth_certificate_issued: "Birth Certificate v2",
  evolution_proof_passed: "Evolution Proof",
  sim_real_guard_stable: "SIM_REAL_GUARD stable (5d)",
  promotion_gate_passed: "Promotion gate (shadow)",
};

export function BirthReadinessLadder({ status, className }: BirthReadinessLadderProps) {
  const [milestonesReached, setMilestonesReached] = useState<string[]>([]);
  const [autopilotNote, setAutopilotNote] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void fetchMaturationProgress()
      .then((payload) => {
        if (cancelled) return;
        setMilestonesReached(
          Array.isArray(payload.milestones_reached) ? payload.milestones_reached : [],
        );
        setAutopilotNote(
          payload.real_trading_eligible
            ? "Maturation autopilot: REAL-ready notification sent"
            : "Maturation autopilot: advancing SIM stability + shadow gate",
        );
      })
      .catch(() => {
        if (!cancelled) {
          setAutopilotNote(null);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [status?.artifacts_ok, status?.certificate_ok]);

  const checks: Record<string, boolean> = {
    birth_certificate_issued: status?.certificate_ok === true,
    evolution_proof_passed: status?.evolution_proof_ok === true,
    sim_real_guard_stable: milestonesReached.includes("sim_real_guard_stable"),
    promotion_gate_passed: milestonesReached.includes("promotion_gate_passed"),
  };

  const passed = REAL_MILESTONE_IDS.filter((id) => checks[id]).length;
  const total = REAL_MILESTONE_IDS.length;

  return (
    <div
      className={cn(
        "rounded-md border border-white/10 bg-black/25 px-3 py-2 text-[10px] font-mono",
        className,
      )}
    >
      <p className="text-[9px] uppercase tracking-wide text-muted-foreground">
        Path to REAL trading — {passed}/{total} milestones
      </p>
      {autopilotNote ? (
        <p className="mt-1 text-[10px] text-cyan-300/80">{autopilotNote}</p>
      ) : (
        <p className="mt-1 text-[10px] text-muted-foreground">
          Birth cert is step 1 of 4. REAL requires sim_real_guard + promotion gate + constitution.
        </p>
      )}
      <ul className="mt-2 space-y-1">
        {REAL_MILESTONE_IDS.map((id) => {
          const ok = checks[id];
          return (
            <li
              key={id}
              className={cn(
                "flex items-center justify-between gap-2",
                ok ? "text-emerald-200/90" : "text-amber-100/80",
              )}
            >
              <span>{REAL_MILESTONE_LABELS[id]}</span>
              <span>{ok ? "✓" : "—"}</span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}