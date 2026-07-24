import { motion } from "framer-motion";
import { Check } from "lucide-react";

import type { BirthMilestone } from "@/lib/birthPhaseModel";
import { usePrefersReducedMotion } from "@/hooks/usePrefersReducedMotion";
import { cn } from "@/lib/utils";

interface BirthMilestoneTrackProps {
  milestones: BirthMilestone[];
  upcomingCount?: number;
  variant?: "default" | "drawer" | "bar";
  className?: string;
}

export function BirthMilestoneTrack({
  milestones,
  upcomingCount = 0,
  variant = "default",
  className,
}: BirthMilestoneTrackProps) {
  const reducedMotion = usePrefersReducedMotion();
  const drawer = variant === "drawer";
  const bar = variant === "bar";

  return (
    <div className={cn("birth-milestone-track-wrap", bar && "birth-milestone-track-wrap--bar", className)}>
      <ol
        className={cn(
          "birth-milestone-track",
          bar && "birth-milestone-track--bar flex flex-nowrap items-center gap-1.5",
          drawer && "flex flex-col gap-2",
          !bar && !drawer && "flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:justify-center sm:gap-6",
        )}
        aria-label="Birth milestones"
      >
        {milestones.map((milestone, index) => (
          <motion.li
            key={milestone.id}
            className={cn(
              "birth-milestone flex shrink-0 items-center gap-2",
              bar &&
                "birth-milestone--bar risk-envelope-status-chip gap-1.5 rounded-full border border-white/10 px-2 py-0.5 text-[9px]",
              drawer && "birth-milestone--drawer rounded-md px-2 py-1.5 text-xs",
              !bar && !drawer && "text-sm",
              milestone.state === "active" && "birth-milestone--active",
              milestone.state === "complete" && "birth-milestone--complete",
            )}
            data-state={
              milestone.state === "active"
                ? "partial"
                : milestone.state === "complete"
                  ? "ok"
                  : undefined
            }
            initial={reducedMotion ? false : { opacity: 0, y: bar ? 0 : 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: reducedMotion ? 0 : index * 0.05, duration: 0.25 }}
          >
            <span
              className={cn(
                "birth-milestone-dot flex shrink-0 items-center justify-center rounded-full border border-white/15",
                bar ? "size-3.5 border-current/30" : "size-6",
              )}
              data-state={milestone.state}
            >
              {milestone.state === "complete" ? (
                <Check className={cn(bar ? "size-2" : "size-3.5", "text-emerald-300")} aria-hidden />
              ) : (
                <span
                  className={cn(
                    "rounded-full bg-current",
                    bar ? "size-1 opacity-80" : "size-1.5 opacity-60",
                  )}
                />
              )}
            </span>
            <span
              className={cn(
                "leading-snug whitespace-nowrap",
                bar && "font-mono text-[9px] tracking-[0.08em] uppercase",
                drawer && "font-mono text-[10px] tracking-wide",
                !bar && !drawer && "max-w-[11rem] text-sm",
                milestone.state === "pending" && "text-muted-foreground",
                milestone.state === "active" && (bar ? "font-medium text-cyan-100" : "text-foreground font-medium"),
                milestone.state === "complete" && "text-emerald-200/90",
              )}
            >
              {milestone.label}
            </span>
          </motion.li>
        ))}
        {bar && upcomingCount > 0 ? (
          <li className="birth-milestone-upcoming shrink-0 font-mono text-[9px] tracking-[0.1em] text-white/35 whitespace-nowrap uppercase">
            +{upcomingCount}
          </li>
        ) : null}
      </ol>
      {!bar && upcomingCount > 0 ? (
        <p className="mt-2 font-mono text-[10px] text-muted-foreground">
          ··· +{upcomingCount} upcoming
        </p>
      ) : null}
    </div>
  );
}
