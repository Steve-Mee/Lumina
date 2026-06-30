import type { BirthSessionHudModel } from "@/lib/birthPhaseModel";
import { cn } from "@/lib/utils";

function formatElapsed(sec: number): string {
  const minutes = Math.floor(sec / 60);
  const seconds = Math.floor(sec % 60);
  return `${minutes}m ${seconds}s`;
}

export function BirthSessionTelemetry({
  hud,
  elapsedSec,
  className,
}: {
  hud: BirthSessionHudModel;
  elapsedSec?: number | null;
  className?: string;
}) {
  const resolvedElapsed =
    elapsedSec != null && elapsedSec >= 0 ? elapsedSec : hud.elapsedSec;
  const sessionLabel =
    hud.sessionStartedAtMs != null ? hud.sessionStartedLabel : "syncing…";

  return (
    <div className={cn("space-y-1 font-mono text-[10px] text-muted-foreground", className)}>
      <p className="text-cyan-200/85">
        Sessie gestart @ {sessionLabel}
        {resolvedElapsed != null ? ` · ${formatElapsed(resolvedElapsed)} elapsed` : ""}
      </p>
      <p>
        Patterns: {hud.patternsMined.toLocaleString()} mined
        {" · "}
        {hud.learningAttempt > 0 ? `attempt ${hud.learningAttempt}` : "attempt —"}
      </p>
      {hud.preCurriculum ? (
        <p className="text-cyan-200/60">
          Stage-scorecard verschijnt zodra curriculum stage 1 start — counters hierboven lopen al
          mee vanaf sessiestart.
        </p>
      ) : null}
    </div>
  );
}
