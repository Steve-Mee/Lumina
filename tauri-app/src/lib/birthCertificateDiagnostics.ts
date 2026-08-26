import type { BirthStatusPayload } from "@/lib/birthClient";

export type CertificateMetricKind = "percent" | "number" | "count" | "regimes";

export interface ParsedFailureToken {
  metricId: string;
  label: string;
  actual: number;
  target: number;
  kind: CertificateMetricKind;
  passed: boolean;
  higherIsBetter: boolean;
}

export interface CertificateDiagnostics {
  certificateOk: boolean;
  failureReasons: string[];
  runwayPhase: string;
  birthExitWinrate: number | null;
  metrics: ParsedFailureToken[];
  holdoutTrades: number | null;
  qualityScore: number | null;
}

const METRIC_META: Record<
  string,
  { label: string; kind: CertificateMetricKind; higherIsBetter: boolean }
> = {
  oos_winrate: { label: "OOS winrate", kind: "percent", higherIsBetter: true },
  oos_sharpe: { label: "OOS Sharpe", kind: "number", higherIsBetter: true },
  oos_max_drawdown_pct: { label: "Max drawdown", kind: "percent", higherIsBetter: false },
  constitution_violations: { label: "Violations", kind: "count", higherIsBetter: false },
  real_data_pct: { label: "Real data", kind: "percent", higherIsBetter: true },
  regimes_covered: { label: "Regimes", kind: "count", higherIsBetter: true },
  holdout_trades: { label: "Holdout trades", kind: "count", higherIsBetter: true },
};

export function parseFailureReasonToken(token: string): ParsedFailureToken | null {
  const text = String(token ?? "").trim();
  const colon = text.indexOf(":");
  if (colon <= 0) return null;
  const metricId = text.slice(0, colon).trim();
  const values = text.slice(colon + 1).trim();
  const slash = values.indexOf("/");
  if (slash <= 0) return null;
  const actual = Number(values.slice(0, slash));
  const target = Number(values.slice(slash + 1));
  if (!Number.isFinite(actual) || !Number.isFinite(target)) return null;

  const meta = METRIC_META[metricId] ?? {
    label: metricId.replace(/_/g, " "),
    kind: "number" as CertificateMetricKind,
    higherIsBetter: true,
  };

  const passed = meta.higherIsBetter ? actual >= target : actual <= target;
  return {
    metricId,
    label: meta.label,
    actual,
    target,
    kind: meta.kind,
    passed,
    higherIsBetter: meta.higherIsBetter,
  };
}

function collectFailureReasons(status: BirthStatusPayload | null): string[] {
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

function resolveOosRecord(status: BirthStatusPayload | null): Record<string, unknown> {
  const direct = status?.oos_metrics;
  if (direct && typeof direct === "object" && Object.keys(direct as object).length > 0) {
    return direct as Record<string, unknown>;
  }
  const progressOos = status?.progress?.oos_metrics;
  if (progressOos && typeof progressOos === "object" && Object.keys(progressOos as object).length > 0) {
    return progressOos as Record<string, unknown>;
  }
  return {};
}

function metricFromOos(
  metricId: string,
  oos: Record<string, unknown>,
): ParsedFailureToken | null {
  const raw = oos[metricId];
  if (raw == null || !Number.isFinite(Number(raw))) return null;
  const meta = METRIC_META[metricId];
  if (!meta) return null;
  return {
    metricId,
    label: meta.label,
    actual: Number(raw),
    target: NaN,
    kind: meta.kind,
    passed: true,
    higherIsBetter: meta.higherIsBetter,
  };
}

const PRIMARY_METRIC_IDS = [
  "oos_winrate",
  "oos_sharpe",
  "oos_max_drawdown_pct",
  "constitution_violations",
  "holdout_trades",
] as const;

export function resolveCertificateDiagnostics(status: BirthStatusPayload | null): CertificateDiagnostics {
  const failureReasons = collectFailureReasons(status);
  const parsed = failureReasons
    .map(parseFailureReasonToken)
    .filter((row): row is ParsedFailureToken => row != null);

  const byId = new Map(parsed.map((row) => [row.metricId, row]));
  const oos = resolveOosRecord(status);
  const cert = status?.certificate;

  for (const metricId of PRIMARY_METRIC_IDS) {
    if (byId.has(metricId)) continue;
    const fromOos = metricFromOos(metricId, oos);
    if (fromOos) byId.set(metricId, fromOos);
    if (metricId === "oos_winrate" && cert?.oos_winrate != null) {
      byId.set(metricId, {
        metricId,
        label: "OOS winrate",
        actual: Number(cert.oos_winrate),
        target: NaN,
        kind: "percent",
        passed: true,
        higherIsBetter: true,
      });
    }
    if (metricId === "oos_sharpe" && cert?.oos_sharpe != null) {
      byId.set(metricId, {
        metricId,
        label: "OOS Sharpe",
        actual: Number(cert.oos_sharpe),
        target: NaN,
        kind: "number",
        passed: true,
        higherIsBetter: true,
      });
    }
    if (metricId === "oos_max_drawdown_pct" && cert?.oos_max_drawdown_pct != null) {
      byId.set(metricId, {
        metricId,
        label: "Max drawdown",
        actual: Number(cert.oos_max_drawdown_pct),
        target: NaN,
        kind: "percent",
        passed: true,
        higherIsBetter: false,
      });
    }
  }

  const metrics = PRIMARY_METRIC_IDS.map((id) => byId.get(id)).filter(
    (row): row is ParsedFailureToken => row != null,
  );

  const holdoutTrades =
    oos.holdout_trades != null && Number.isFinite(Number(oos.holdout_trades))
      ? Number(oos.holdout_trades)
      : null;

  return {
    certificateOk: status?.certificate_ok === true,
    failureReasons,
    runwayPhase: String(status?.runway_phase ?? status?.progress?.runway_phase ?? "").trim(),
    birthExitWinrate:
      status?.birth_exit_winrate != null
        ? Number(status.birth_exit_winrate)
        : status?.progress?.birth_exit_winrate != null
          ? Number(status.progress.birth_exit_winrate)
          : null,
    metrics,
    holdoutTrades,
    qualityScore: status?.quality_score != null ? Number(status.quality_score) : null,
  };
}

export function formatMetricValue(
  kind: CertificateMetricKind,
  value: number,
  metricId?: string,
): string {
  if (!Number.isFinite(value)) return "—";
  if (kind === "percent") {
    const isFraction =
      metricId === "oos_winrate" || (Math.abs(value) <= 1.0 && metricId !== "oos_max_drawdown_pct");
    if (isFraction) return `${(value * 100).toFixed(1)}%`;
    return `${value.toFixed(1)}%`;
  }
  if (kind === "count") return String(Math.round(value));
  return value.toFixed(2);
}

export function formatMetricTarget(row: ParsedFailureToken): string {
  if (!Number.isFinite(row.target)) return "—";
  if (row.kind === "percent") {
    const prefix = row.higherIsBetter ? "≥" : "≤";
    const isFraction =
      row.metricId === "oos_winrate" ||
      (Math.abs(row.target) <= 1.0 && row.metricId !== "oos_max_drawdown_pct");
    const display = isFraction ? row.target * 100 : row.target;
    return `${prefix} ${display.toFixed(1)}%`;
  }
  if (row.kind === "count") {
    const prefix = row.higherIsBetter ? "≥" : "≤";
    return `${prefix} ${Math.round(row.target)}`;
  }
  const prefix = row.higherIsBetter ? "≥" : "≤";
  return `${prefix} ${row.target.toFixed(2)}`;
}

export function resolveCertificateFailureSubtitle(status: BirthStatusPayload | null): string {
  const diag = resolveCertificateDiagnostics(status);
  const runway = diag.runwayPhase;
  if (runway) {
    return `Generalization gap — certificate OOS belongs in Proving Ground (${runway}).`;
  }
  if (status?.fast_path_eligible) {
    return "Birth Foundation complete — certificate OOS 0.48 is Proving Ground, not Birth exit.";
  }
  return "Holdout evaluation did not meet Birth Certificate v2 thresholds.";
}
