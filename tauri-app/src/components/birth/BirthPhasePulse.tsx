import type { CSSProperties } from "react";

import type { BirthMilestone } from "@/lib/birthPhaseModel";
import type { BirthProgressPayload } from "@/lib/birthClient";
import { BIRTH_MILESTONE_ORDER } from "@/lib/birthPhaseModel";
import { cn } from "@/lib/utils";

interface BirthPhasePulseProps {
  running: boolean;
  milestones: BirthMilestone[];
  progress?: BirthProgressPayload;
  className?: string;
}

function resolvePulseFill(
  milestones: BirthMilestone[],
  progress?: BirthProgressPayload,
): number {
  if (progress?.progress_pct != null) {
    return Math.min(1, Math.max(0, progress.progress_pct / 100));
  }
  const activeIndex = milestones.findIndex((m) => m.state === "active");
  const completed = milestones.filter((m) => m.state === "complete").length;
  if (activeIndex >= 0) {
    return (activeIndex + 0.45) / BIRTH_MILESTONE_ORDER.length;
  }
  return completed / BIRTH_MILESTONE_ORDER.length;
}

export function BirthPhasePulse({
  running,
  milestones,
  progress,
  className,
}: BirthPhasePulseProps) {
  if (!running) {
    return null;
  }

  const fill = resolvePulseFill(milestones, progress);

  return (
    <div
      className={cn("birth-phase-pulse", className)}
      aria-hidden
      style={{ "--birth-pulse-fill": fill } as CSSProperties}
    >
      <span className="birth-phase-pulse__ring" />
      <span className="birth-phase-pulse__core" />
      <span className="sr-only">Birth phase {Math.round(fill * 100)} percent</span>
    </div>
  );
}
