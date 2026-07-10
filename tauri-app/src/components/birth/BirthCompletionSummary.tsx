import type { BirthStatusPayload } from "@/lib/birthClient";
import {
  formatMetricTarget,
  formatMetricValue,
  resolveCertificateDiagnostics,
} from "@/lib/birthCertificateDiagnostics";
import { cn } from "@/lib/utils";

import { BirthReadinessLadder } from "./BirthReadinessLadder";

interface BirthCompletionSummaryProps {
  status: BirthStatusPayload | null;
  className?: string;
}

export function BirthCompletionSummary({ status, className }: BirthCompletionSummaryProps) {
  const progress = status?.progress;
  const cert = status?.certificate;
  const diag = resolveCertificateDiagnostics(status);

  if (!progress && !cert) return null;

  const certificateOk = diag.certificateOk;
  const regimes = cert?.regimes_covered ?? (status?.oos_metrics?.regimes_covered as string[] | undefined);
  const regimeList = Array.isArray(regimes) ? regimes.join(", ") : "—";

  return (
    <section
      className={cn(
        "birth-completion-summary rounded-xl border p-5 text-sm shadow-lg",
        certificateOk ? "birth-completion-summary--ok" : "birth-completion-summary--fail",
        className,
      )}
    >
      <h4 className="mb-3 text-center font-mono text-[10px] tracking-[0.16em] uppercase text-emerald-200/90">
        {certificateOk ? "Birth Certificate issued" : "Certificate evaluation — not passed"}
      </h4>

      {!certificateOk ? <BirthReadinessLadder status={status} className="mb-4" /> : null}

      {diag.metrics.length > 0 ? (
        <div className="overflow-x-auto rounded-md border border-white/10 bg-black/30">
          <table className="w-full min-w-[280px] font-mono text-[11px]">
            <thead>
              <tr className="border-b border-white/10 text-[9px] uppercase text-muted-foreground">
                <th className="px-3 py-2 text-left font-normal">Metric</th>
                <th className="px-3 py-2 text-right font-normal">Actual</th>
                <th className="px-3 py-2 text-right font-normal">Required</th>
                <th className="px-3 py-2 text-center font-normal">Status</th>
              </tr>
            </thead>
            <tbody>
              {diag.metrics.map((row) => (
                <tr key={row.metricId} className="border-b border-white/5 last:border-0">
                  <td className="px-3 py-2 text-emerald-100/90">{row.label}</td>
                  <td className="px-3 py-2 text-right text-cyan-200/90">
                    {formatMetricValue(row.kind, row.actual, row.metricId)}
                  </td>
                  <td className="px-3 py-2 text-right text-muted-foreground">
                    {formatMetricTarget(row)}
                  </td>
                  <td className="px-3 py-2 text-center">
                    {Number.isFinite(row.target) ? (
                      <span className={row.passed ? "text-emerald-400" : "text-rose-400"}>
                        {row.passed ? "✓" : "✗"}
                      </span>
                    ) : (
                      <span className="text-muted-foreground">—</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}

      {regimeList !== "—" ? (
        <p className="mt-3 font-mono text-[10px] text-muted-foreground">
          Regimes covered: <span className="text-emerald-200/90">{regimeList}</span>
        </p>
      ) : null}

      {diag.qualityScore != null ? (
        <p className="mt-3 text-center font-mono text-[10px] text-muted-foreground">
          Research quality score: {diag.qualityScore.toFixed(3)}
        </p>
      ) : null}
    </section>
  );
}
