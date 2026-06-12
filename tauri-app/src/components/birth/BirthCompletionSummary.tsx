import type { BirthStatusPayload } from "@/lib/birthClient";
import { cn } from "@/lib/utils";

interface BirthCompletionSummaryProps {
  status: BirthStatusPayload | null;
  className?: string;
}

function fmtPct(value: unknown, digits = 1): string {
  const n = Number(value);
  if (!Number.isFinite(n)) return "—";
  return `${(n * 100).toFixed(digits)}%`;
}

function fmtNum(value: unknown, digits = 2): string {
  const n = Number(value);
  if (!Number.isFinite(n)) return "—";
  return n.toFixed(digits);
}

export function BirthCompletionSummary({ status, className }: BirthCompletionSummaryProps) {
  const progress = status?.progress;
  const cert = status?.certificate;
  const oos = (status?.oos_metrics ?? progress?.oos_metrics ?? {}) as Record<string, unknown>;

  if (!progress && !cert) return null;

  const certificateOk = status?.certificate_ok === true;
  const winrate = cert?.oos_winrate ?? oos.oos_winrate;
  const sharpe = cert?.oos_sharpe ?? oos.oos_sharpe;
  const drawdown = cert?.oos_max_drawdown_pct ?? oos.oos_max_drawdown_pct;
  const violations = cert?.constitution_violations ?? oos.constitution_violations;
  const regimes = cert?.regimes_covered ?? progress?.regimes_covered ?? oos.regimes_covered;
  const regimeList = Array.isArray(regimes) ? regimes.join(", ") : "—";

  return (
    <section
      className={cn(
        "rounded-lg border p-4 text-sm",
        certificateOk
          ? "border-emerald-500/25 bg-emerald-950/20"
          : "border-amber-500/25 bg-amber-950/20",
        className,
      )}
    >
      <h4 className="mb-3 font-mono text-[10px] tracking-[0.16em] uppercase text-emerald-200/90">
        Birth complete — OOS summary
      </h4>
      <div className="grid grid-cols-2 gap-2 font-mono text-xs sm:grid-cols-3">
        <div className="rounded border border-white/10 bg-black/25 px-2 py-1.5">
          <p className="text-[9px] text-muted-foreground uppercase">Certificate</p>
          <p className={certificateOk ? "text-emerald-200/90" : "text-amber-200/90"}>
            {certificateOk ? "OK" : status?.certificate_reason ?? "Failed"}
          </p>
        </div>
        <div className="rounded border border-white/10 bg-black/25 px-2 py-1.5">
          <p className="text-[9px] text-muted-foreground uppercase">OOS winrate</p>
          <p className="text-cyan-200/90">{fmtPct(winrate)}</p>
        </div>
        <div className="rounded border border-white/10 bg-black/25 px-2 py-1.5">
          <p className="text-[9px] text-muted-foreground uppercase">OOS Sharpe</p>
          <p className="text-violet-200/90">{fmtNum(sharpe)}</p>
        </div>
        <div className="rounded border border-white/10 bg-black/25 px-2 py-1.5">
          <p className="text-[9px] text-muted-foreground uppercase">Max drawdown</p>
          <p className="text-rose-200/90">{fmtNum(drawdown, 1)}%</p>
        </div>
        <div className="rounded border border-white/10 bg-black/25 px-2 py-1.5">
          <p className="text-[9px] text-muted-foreground uppercase">Violations</p>
          <p className="text-emerald-200/90">{String(violations ?? "—")}</p>
        </div>
        <div className="rounded border border-white/10 bg-black/25 px-2 py-1.5 sm:col-span-3">
          <p className="text-[9px] text-muted-foreground uppercase">Regimes covered</p>
          <p className="truncate text-emerald-200/90">{regimeList}</p>
        </div>
      </div>
      {status?.message ? (
        <p className="mt-3 text-xs text-muted-foreground">{status.message}</p>
      ) : null}
    </section>
  );
}
