import { Brain } from "lucide-react";

import { DeckMetricTile } from "@/components/cockpit/DeckMetricTile";
import { DeckSection } from "@/components/cockpit/DeckSection";
import {
  formatCalibrationSummary,
  formatConfidenceDistribution,
  formatRollingAgreement,
  formatTwinNum,
  formatTwinPct,
  type TwinMetrics,
} from "@/lib/twinClient";

export interface TwinTrainMetricsSectionProps {
  metrics: TwinMetrics | null;
}

export function TwinTrainMetricsSection({ metrics }: TwinTrainMetricsSectionProps) {
  const riskTop = metrics?.risk_flag_top ?? {};
  const riskTopEntries = Object.entries(riskTop).slice(0, 6);
  const confLine = formatConfidenceDistribution(metrics?.confidence_distribution);
  const rollingLine = formatRollingAgreement(metrics?.rolling_agreement);
  const calibLine = formatCalibrationSummary(metrics?.calibration);
  const agreementSeries = (metrics?.agreement_over_time ?? []).slice(-5);

  return (
    <DeckSection title="Twin metrics" icon={Brain}>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        <DeckMetricTile
          label="vs Steve"
          value={
            metrics?.twin_steve_agreement_pct != null
              ? formatTwinPct(metrics.twin_steve_agreement_pct)
              : "—"
          }
        />
        <DeckMetricTile
          label="Mode agree"
          value={
            metrics?.twin_agreement_pct != null
              ? formatTwinPct(metrics.twin_agreement_pct)
              : "—"
          }
        />
        <DeckMetricTile
          label="Rolling w50"
          value={
            metrics?.rolling_agreement?.w50 != null
              ? formatTwinPct(metrics.rolling_agreement.w50)
              : "—"
          }
        />
        <DeckMetricTile label="Reward" value={formatTwinNum(metrics?.reward)} />
        <DeckMetricTile
          label="Avg error"
          value={formatTwinNum(metrics?.avg_prediction_error)}
        />
        <DeckMetricTile
          label="High-conf agree"
          value={
            metrics?.calibration?.high_conf_agreement_pct != null
              ? formatTwinPct(metrics.calibration.high_conf_agreement_pct)
              : "—"
          }
        />
        <DeckMetricTile
          label="Calib |err|"
          value={formatTwinNum(metrics?.calibration?.mean_abs_calibration_error)}
        />
        <DeckMetricTile
          label="Risk caught"
          value={
            metrics?.risk_flags_caught != null
              ? `${metrics.risk_flags_caught}${
                  metrics.risk_flags_catch_rate_pct != null
                    ? ` (${formatTwinPct(metrics.risk_flags_catch_rate_pct)})`
                    : ""
                }`
              : "—"
          }
        />
        <DeckMetricTile
          label="Risk missed"
          value={
            metrics?.risk_flags_missed != null
              ? `${metrics.risk_flags_missed}${
                  metrics.risk_flags_missed_pct != null
                    ? ` (${formatTwinPct(metrics.risk_flags_missed_pct)})`
                    : ""
                }`
              : "—"
          }
        />
        <DeckMetricTile
          label="False + %"
          value={
            metrics?.false_positive_pct != null
              ? formatTwinPct(metrics.false_positive_pct)
              : "—"
          }
        />
        <DeckMetricTile
          label="Steps"
          value={String(metrics?.training_steps ?? "—")}
        />
        <DeckMetricTile
          label="Labels"
          value={String(metrics?.labels_total_recent_cap ?? "—")}
        />
      </div>
      <p className="mt-2 font-mono text-[10px] text-muted-foreground">
        Rolling: {rollingLine}
      </p>
      <p className="mt-0.5 font-mono text-[10px] text-muted-foreground">
        Calibration: {calibLine}
      </p>
      <p className="mt-0.5 font-mono text-[10px] text-muted-foreground">
        Confidence hist: {confLine}
      </p>
      {agreementSeries.length > 0 ? (
        <p className="mt-0.5 font-mono text-[10px] text-muted-foreground">
          Agree over time:{" "}
          {agreementSeries
            .map(
              (p) =>
                `${p.period ?? "?"} ${
                  p.agreement_pct != null ? formatTwinPct(p.agreement_pct) : "—"
                }`,
            )
            .join(" · ")}
        </p>
      ) : null}
      {riskTopEntries.length > 0 ? (
        <div className="mt-2 flex flex-wrap gap-1.5">
          <span className="font-mono text-[9px] tracking-wider text-muted-foreground uppercase">
            Risk flags
          </span>
          {riskTopEntries.map(([flag, count]) => (
            <span
              key={flag}
              className="rounded bg-amber-500/15 px-1.5 py-0.5 font-mono text-[9px] text-amber-100/90"
            >
              {flag}×{count}
            </span>
          ))}
        </div>
      ) : (
        <p className="mt-1 text-[10px] text-muted-foreground">
          No risk flags in recent decision window.
        </p>
      )}
      {metrics?.outcome_counts ? (
        <p className="mt-1 font-mono text-[10px] text-muted-foreground">
          Outcomes: auto {metrics.outcome_counts.auto_approved ?? 0} · veto{" "}
          {metrics.outcome_counts.veto ?? 0} · deferred{" "}
          {metrics.outcome_counts.deferred ?? 0} · other{" "}
          {metrics.outcome_counts.other ?? 0}
          {metrics.decisions_total != null
            ? ` · window ${metrics.decisions_total}`
            : ""}
        </p>
      ) : null}
    </DeckSection>
  );
}
