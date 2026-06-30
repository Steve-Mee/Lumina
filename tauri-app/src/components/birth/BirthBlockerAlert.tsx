import { extractStageScorecard } from "@/lib/birthPhaseModel";
import type { BirthProgressPayload } from "@/lib/birthClient";
import { cn } from "@/lib/utils";

interface BirthBlockerAlertProps {
  progress: BirthProgressPayload | undefined;
  className?: string;
}

export function BirthBlockerAlert({ progress, className }: BirthBlockerAlertProps) {
  const scorecard = extractStageScorecard(progress);
  if (!scorecard?.blockerDetail) {
    return null;
  }

  return (
    <div
      className={cn(
        "birth-blocker-alert shrink-0 rounded-md border border-amber-500/30 bg-amber-950/20 px-3 py-1.5",
        className,
      )}
      role="status"
    >
      <p className="font-mono text-[10px] tracking-wide text-amber-200/90 uppercase">
        {scorecard.blockerLabel ?? "Blocking metric"}
      </p>
      <p className="mt-0.5 truncate font-mono text-xs text-amber-100" title={scorecard.blockerDetail}>
        {scorecard.blockerDetail}
      </p>
    </div>
  );
}
