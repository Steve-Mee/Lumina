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
      className={cn("birth-blocker-alert birth-distress-callout shrink-0 rounded-md px-3 py-1.5", className)}
      role="status"
    >
      <p className="birth-distress-callout__title tracking-wide">
        {scorecard.blockerLabel ?? "Blocking metric"}
      </p>
      <p className="birth-distress-callout__body mt-0.5 truncate" title={scorecard.blockerDetail}>
        {scorecard.blockerDetail}
      </p>
    </div>
  );
}
