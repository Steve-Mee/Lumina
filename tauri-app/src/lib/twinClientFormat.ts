/** Twin display/format helpers (store/HUD residual split). */
import type {
  TwinCalibration,
  TwinConfidenceDistribution,
  TwinPromotionCriterionProgress,
  TwinReviewItem,
  TwinRollingAgreement,
} from "@/lib/twinClientTypes";

export function twinScoreOf(item: TwinReviewItem): number | null {
  const raw = item.score ?? item.confidence;
  if (typeof raw === "number" && Number.isFinite(raw)) return raw;
  if (typeof raw === "string") {
    const n = Number(raw);
    return Number.isFinite(n) ? n : null;
  }
  return null;
}

/** Format agreement-style percentages (0–1 or already 0–100). */
export function formatTwinPct(v: number | null | undefined): string {
  if (v == null || Number.isNaN(Number(v))) return "—";
  const n = Number(v);
  if (n <= 1.5) return `${(n * 100).toFixed(1)}%`;
  return `${n.toFixed(1)}%`;
}

export function formatTwinNum(v: number | null | undefined, digits = 3): string {
  if (v == null || Number.isNaN(Number(v))) return "—";
  return Number(v).toFixed(digits);
}

export function formatConfidenceDistribution(
  dist: TwinConfidenceDistribution | null | undefined,
): string {
  if (!dist || !dist.n) return "No scored decisions in window";
  return `n=${dist.n} · <50 ${dist.lt_50 ?? 0} · 50–60 ${dist.b50_60 ?? 0} · 60–80 ${dist.b60_80 ?? 0} · ≥80 ${dist.gte_80 ?? 0}`;
}

export function formatRollingAgreement(
  rolling: TwinRollingAgreement | null | undefined,
): string {
  if (!rolling) return "—";
  const parts: string[] = [];
  if (rolling.w20 != null) parts.push(`w20 ${formatTwinPct(rolling.w20)}`);
  if (rolling.w50 != null) parts.push(`w50 ${formatTwinPct(rolling.w50)}`);
  if (rolling.w100 != null) parts.push(`w100 ${formatTwinPct(rolling.w100)}`);
  return parts.length ? parts.join(" · ") : "—";
}

export function formatCalibrationSummary(
  calib: TwinCalibration | null | undefined,
): string {
  if (!calib || !calib.scored_samples) return "No scored comparisons yet";
  const high =
    calib.high_conf_agreement_pct != null
      ? formatTwinPct(calib.high_conf_agreement_pct)
      : "—";
  const err =
    calib.mean_abs_calibration_error != null
      ? formatTwinNum(calib.mean_abs_calibration_error, 3)
      : "—";
  return `scored ${calib.scored_samples} · high-conf agree ${high} · |calib err| ${err}`;
}

/** Compact progress bar ratio 0–1 for mode promotion criteria. */
export function promotionRatio(value: TwinPromotionCriterionProgress | null | undefined): number {
  if (!value || typeof value.ratio !== "number" || Number.isNaN(value.ratio)) return 0;
  return Math.max(0, Math.min(1, value.ratio));
}
