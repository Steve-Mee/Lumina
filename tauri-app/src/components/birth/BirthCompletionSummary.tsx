import type { BirthStatusPayload } from "@/lib/birthClient";
import { cn } from "@/lib/utils";

interface BirthCompletionSummaryProps {
  status: BirthStatusPayload | null;
  className?: string;
}

export function BirthCompletionSummary({ status, className }: BirthCompletionSummaryProps) {
  const progress = status?.progress;
  if (!progress) return null;

  const trades = Number(progress.cumulative_trades ?? progress.trades_done ?? 0);
  const ppo = Number(progress.ppo_steps ?? progress.ppo_steps_cumulative ?? 0);
  const stage = String(progress.stage ?? status?.status ?? "complete");

  return (
    <section
      className={cn(
        "rounded-lg border border-emerald-500/25 bg-emerald-950/20 p-4 text-sm",
        className,
      )}
    >
      <h4 className="mb-3 font-mono text-[10px] tracking-[0.16em] text-emerald-200/90 uppercase">
        Birth complete — summary
      </h4>
      <div className="grid grid-cols-2 gap-2 font-mono text-xs sm:grid-cols-4">
        <div className="rounded border border-white/10 bg-black/25 px-2 py-1.5">
          <p className="text-[9px] text-muted-foreground uppercase">Stage</p>
          <p className="text-emerald-200/90">{stage}</p>
        </div>
        <div className="rounded border border-white/10 bg-black/25 px-2 py-1.5">
          <p className="text-[9px] text-muted-foreground uppercase">Trades</p>
          <p className="text-cyan-200/90">{trades.toLocaleString()}</p>
        </div>
        <div className="rounded border border-white/10 bg-black/25 px-2 py-1.5">
          <p className="text-[9px] text-muted-foreground uppercase">PPO steps</p>
          <p className="text-violet-200/90">{ppo.toLocaleString()}</p>
        </div>
        <div className="rounded border border-white/10 bg-black/25 px-2 py-1.5">
          <p className="text-[9px] text-muted-foreground uppercase">Artifacts</p>
          <p className="text-emerald-200/90">{status?.artifacts_ok ? "OK" : "Pending"}</p>
        </div>
      </div>
      {status?.message ? (
        <p className="mt-3 text-xs text-muted-foreground">{status.message}</p>
      ) : null}
    </section>
  );
}
