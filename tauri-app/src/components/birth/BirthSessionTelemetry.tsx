import type { BirthSessionHudModel } from "@/lib/birthPhaseModel";
import { cn } from "@/lib/utils";

import { BirthFieldCard } from "@/components/birth/BirthFieldCard";

function formatElapsed(sec: number): string {
  const minutes = Math.floor(sec / 60);
  const seconds = Math.floor(sec % 60);
  return `${minutes}m ${seconds}s`;
}

export function BirthSessionTelemetry({
  hud,
  elapsedSec,
  className,
  /** When true, fields are direct grid children (no nested grid wrapper). */
  embeddedGrid = false,
}: {
  hud: BirthSessionHudModel;
  elapsedSec?: number | null;
  className?: string;
  embeddedGrid?: boolean;
}) {
  const resolvedElapsed =
    elapsedSec != null && elapsedSec >= 0 ? elapsedSec : hud.elapsedSec;
  const sessionLabel =
    hud.sessionStartedAtMs != null ? hud.sessionStartedLabel : "syncing…";

  const fields = (
    <>
      <BirthFieldCard
        label="Session start"
        value={sessionLabel}
        hint={
          resolvedElapsed != null ? `${formatElapsed(resolvedElapsed)} elapsed` : undefined
        }
      />
      <BirthFieldCard
        label="Patterns mined"
        value={hud.patternsMined.toLocaleString()}
        hint={
          hud.learningAttempt > 0 ? `attempt ${hud.learningAttempt}` : "attempt —"
        }
      />
      {hud.preCurriculum ? (
        <BirthFieldCard
          label="Scorecard"
          value="Pending stage 1"
          hint="Counters above already run from session start"
          className="birth-intel-field-span"
        />
      ) : null}
    </>
  );

  if (embeddedGrid) {
    return fields;
  }

  return (
    <div className={cn("birth-session-telemetry birth-intel-field-grid", className)}>
      {fields}
    </div>
  );
}
