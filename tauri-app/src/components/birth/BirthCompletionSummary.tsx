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

function resolveFailureReasons(status: BirthStatusPayload | null): string[] {
  const direct = status?.failure_reasons;
  if (Array.isArray(direct) && direct.length > 0) {
    return direct.map(String);
  }
  const progressReasons = status?.progress?.failure_reasons;
  if (Array.isArray(progressReasons) && progressReasons.length > 0) {
    return progressReasons.map(String);
  }
  const oos = (status?.oos_metrics ?? status?.progress?.oos_metrics ?? {}) as Record<string, unknown>;
  const oosReasons = oos.failure_reasons;
  if (Array.isArray(oosReasons) && oosReasons.length > 0) {
    return oosReasons.map(String);
  }
  return [];
}

export function BirthCompletionSummary({ status, className }: BirthCompletionSummaryProps) {
  const progress = status?.progress;
  const cert = status?.certificate;
  const oos = (status?.oos_metrics ?? progress?.oos_metrics ?? {}) as Record<string, unknown>;
  const failureReasons = resolveFailureReasons(status);

  if (!progress && !cert) return null;

  const certificateOk = status?.certificate_ok === true;
  const winrate = cert?.oos_winrate ?? oos.oos_winrate;
  const sharpe = cert?.oos_sharpe ?? oos.oos_sharpe;
  const drawdown = cert?.oos_max_drawdown_pct ?? oos.oos_max_drawdown_pct;
  const violations = cert?.constitution_violations ?? oos.constitution_violations;
  const regimes = cert?.regimes_covered ?? progress?.regimes_covered ?? oos.regimes_covered;
  const regimeList = Array.isArray(regimes) ? regimes.join(", ") : "—";
  const holdoutTrades = oos.holdout_trades;

  return (
    <section
      className={cn(
        "birth-completion-summary rounded-xl border p-5 text-sm shadow-lg",
        certificateOk
          ? "border-emerald-500/30 bg-emerald-950/25"
          : "border-amber-500/30 bg-amber-950/25",
        className,
      )}
    >
      <h4 className="mb-4 text-center font-mono text-[10px] tracking-[0.16em] uppercase text-emerald-200/90">
        Birth complete — OOS summary
      </h4>

      {!certificateOk && failureReasons.length > 0 ? (
        <div className="mb-4 rounded-md border border-amber-500/30 bg-black/30 px-3 py-2">
          <p className="text-[9px] text-muted-foreground uppercase">Certificate failure breakdown</p>
          <ul className="mt-2 space-y-1 font-mono text-[11px] text-amber-100/90">
            {failureReasons.map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
          </ul>
        </div>
      ) : null}

      <div className="grid grid-cols-1 gap-3 font-mono text-xs sm:grid-cols-2 lg:grid-cols-3">
        <div className="rounded-md border border-white/10 bg-black/30 px-3 py-2">
          <p className="text-[9px] text-muted-foreground uppercase">OOS winrate</p>
          <p className="mt-1 text-cyan-200/90">{fmtPct(winrate)}</p>
        </div>
        <div className="rounded-md border border-white/10 bg-black/30 px-3 py-2">
          <p className="text-[9px] text-muted-foreground uppercase">OOS Sharpe</p>
          <p className="mt-1 text-violet-200/90">{fmtNum(sharpe)}</p>
        </div>
        <div className="rounded-md border border-white/10 bg-black/30 px-3 py-2">
          <p className="text-[9px] text-muted-foreground uppercase">Max drawdown</p>
          <p className="mt-1 text-rose-200/90">{fmtNum(drawdown, 1)}%</p>
        </div>
        <div className="rounded-md border border-white/10 bg-black/30 px-3 py-2">
          <p className="text-[9px] text-muted-foreground uppercase">Violations</p>
          <p className="mt-1 text-emerald-200/90">{String(violations ?? "—")}</p>
        </div>
        <div className="rounded-md border border-white/10 bg-black/30 px-3 py-2">
          <p className="text-[9px] text-muted-foreground uppercase">Holdout trades</p>
          <p className="mt-1 text-emerald-200/90">{String(holdoutTrades ?? "—")}</p>
        </div>
        <div className="rounded-md border border-white/10 bg-black/30 px-3 py-2 sm:col-span-2 lg:col-span-3">
          <p className="text-[9px] text-muted-foreground uppercase">Regimes covered</p>
          <p className="mt-1 break-words text-emerald-200/90">{regimeList}</p>
        </div>
      </div>
      {status?.quality_score != null ? (
        <p className="mt-3 text-center font-mono text-[10px] text-muted-foreground">
          Research quality score: {fmtNum(status.quality_score, 3)}
        </p>
      ) : null}
      {status?.message ? (
        <p className="mt-4 text-center text-xs text-muted-foreground">{status.message}</p>
      ) : null}
    </section>
  );
}
