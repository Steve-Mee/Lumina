/** Apprenticeship-focus Phase Hub tiles — same glass language as Birth/Awakening. */
import type { MaturityHubPayload } from "@/lib/maturationClient";

type HubCharterTile = {
  label: string;
  value: string;
  tip: string;
  footnote: string;
};

function asFiniteNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim() !== "") {
    const n = Number(value);
    return Number.isFinite(n) ? n : null;
  }
  return null;
}

function formatPct(value: unknown): string {
  const n = asFiniteNumber(value);
  if (n == null) return "—";
  const ratio = Math.abs(n) <= 1.5 ? n : n / 100;
  return `${(ratio * 100).toFixed(1)}%`;
}

function formatScore(value: unknown, digits = 2): string {
  const n = asFiniteNumber(value);
  if (n == null) return "—";
  return n.toFixed(digits);
}

function yn(value: unknown): string {
  if (value === true) return "yes";
  if (value === false) return "no";
  return "—";
}

export function apprenticeshipTilesFromLearned(
  learned: Record<string, unknown>,
): HubCharterTile[] {
  const nD = asFiniteNumber(learned.n_d);
  const riskEvents = asFiniteNumber(learned.risk_events) ?? 0;
  const varBreach = asFiniteNumber(learned.var_breach_count) ?? 0;
  const constitutionOk =
    learned.daily_kill === true || learned.envelope_breached === true || riskEvents > 0 || varBreach > 0
      ? "no"
      : yn(learned.risk_events === 0 || learned.risk_events == null);
  return [
    {
      label: "Doel",
      value: "Lopen",
      tip: "REAL rules, SIM capital. Multi-day walk. Not Playground crawl. Not REAL money.",
      footnote: "5 green days · Sharpe ≥ 0.20 · DD ≤ 12%",
    },
    {
      label: "Groene dagen",
      value: nD == null ? "0 / 5" : `${Math.round(nD)} / 5`,
      tip: "Consecutive futures session days with positive expectancy. Backtest JSON is not a day.",
      footnote: "Fri→Mon counts · weekend is not a gap",
    },
    {
      label: "Sharpe",
      value: formatScore(learned.sharpe),
      tip: "Daily-return Sharpe × √252 on this tape. Floor 0.20. Missing if <5 days or std=0.",
      footnote: "Need ≥ 0.20",
    },
    {
      label: "DD",
      value: formatPct(learned.dd_pct),
      tip: "Peak-to-trough of MES 1-lot equity vs $50k. Ceiling 12%.",
      footnote: "Need ≤ 12%",
    },
    {
      label: "Constitution",
      value: constitutionOk === "no" ? "breach" : "0",
      tip: "risk_events=0, var_breach=0, envelope intact, never REAL.",
      footnote: "sim_real_guard only",
    },
    {
      label: "Recovery",
      value: yn(learned.recovery_ok),
      tip: "Never-stop: resume the same tape. No wipe, no expand_data, no floor-cut.",
      footnote: "Freeze held through ≥1 session",
    },
  ];
}

export function apprenticeshipCharterTiles(hub: MaturityHubPayload | null): HubCharterTile[] {
  return apprenticeshipTilesFromLearned(hub?.focus_learned ?? {});
}
