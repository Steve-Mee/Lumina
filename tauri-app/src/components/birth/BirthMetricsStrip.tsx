import type { BirthProgressPayload } from "@/lib/birthClient";
import { extractPpoProgress, extractSimProgress } from "@/lib/birthPhaseModel";
import { cn } from "@/lib/utils";

interface BirthMetricsStripProps {
  progress: BirthProgressPayload | undefined;
  elapsedSeconds?: number;
  message?: string;
  className?: string;
}

function ProgressBar({
  label,
  value,
  detail,
}: {
  label: string;
  value: number;
  detail: string;
}) {
  const pct = Math.min(100, Math.max(0, value));
  return (
    <div className="birth-metric-bar space-y-1.5">
      <div className="flex items-baseline justify-between gap-2 text-xs">
        <span className="tracking-wide text-muted-foreground uppercase">{label}</span>
        <span className="font-mono text-[11px] text-cyan-200/90">{detail}</span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-white/8">
        <div
          className="birth-metric-bar-fill h-full rounded-full bg-gradient-to-r from-cyan-500/80 to-violet-400/80 transition-[width] duration-500 ease-out"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

export function BirthMetricsStrip({
  progress,
  elapsedSeconds,
  message,
  className,
}: BirthMetricsStripProps) {
  const sim = extractSimProgress(progress);
  const ppo = extractPpoProgress(progress);
  const overallPct = Number(progress?.progress_pct ?? sim.pct);

  const elapsedLabel =
    elapsedSeconds != null && elapsedSeconds > 0
      ? `${Math.floor(elapsedSeconds / 60)}m ${elapsedSeconds % 60}s`
      : null;

  return (
    <div className={cn("birth-metrics-strip space-y-4", className)}>
      <ProgressBar
        label="Simulation trades"
        value={sim.pct}
        detail={
          sim.target > 0
            ? `${sim.done.toLocaleString()} / ${sim.target.toLocaleString()}`
            : `${sim.done.toLocaleString()} trades`
        }
      />
      {ppo.steps > 0 ? (
        <ProgressBar label="PPO refinement" value={overallPct} detail={ppo.label} />
      ) : (
        <ProgressBar
          label="Overall progress"
          value={overallPct}
          detail={`${overallPct.toFixed(1)}%`}
        />
      )}
      <div className="flex flex-wrap items-center justify-between gap-2 text-[11px] text-muted-foreground">
        {elapsedLabel ? <span>Elapsed {elapsedLabel}</span> : <span />}
        {message ? <span className="max-w-md truncate text-cyan-200/70">{message}</span> : null}
      </div>
    </div>
  );
}
