import { motion } from "framer-motion";
import { Check } from "lucide-react";

import type { BirthMilestone } from "@/lib/birthPhaseModel";
import { usePrefersReducedMotion } from "@/hooks/usePrefersReducedMotion";
import { cn } from "@/lib/utils";

interface BirthMilestoneTrackProps {
  milestones: BirthMilestone[];
  className?: string;
}

export function BirthMilestoneTrack({ milestones, className }: BirthMilestoneTrackProps) {
  const reducedMotion = usePrefersReducedMotion();

  return (
    <ol
      className={cn(
        "birth-milestone-track flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:justify-center sm:gap-6",
        className,
      )}
      aria-label="Birth milestones"
    >
      {milestones.map((milestone, index) => (
        <motion.li
          key={milestone.id}
          className={cn(
            "birth-milestone flex items-center gap-2 text-sm",
            milestone.state === "active" && "birth-milestone--active",
            milestone.state === "complete" && "birth-milestone--complete",
          )}
          initial={reducedMotion ? false : { opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: reducedMotion ? 0 : index * 0.08, duration: 0.35 }}
        >
          <span
            className="birth-milestone-dot flex size-6 shrink-0 items-center justify-center rounded-full border border-white/15"
            data-state={milestone.state}
          >
            {milestone.state === "complete" ? (
              <Check className="size-3.5 text-emerald-300" aria-hidden />
            ) : (
              <span className="size-2 rounded-full bg-current opacity-60" />
            )}
          </span>
          <span
            className={cn(
              "max-w-[11rem] leading-snug",
              milestone.state === "pending" && "text-muted-foreground",
              milestone.state === "active" && "text-foreground font-medium",
              milestone.state === "complete" && "text-emerald-200/90",
            )}
          >
            {milestone.label}
          </span>
        </motion.li>
      ))}
    </ol>
  );
}
