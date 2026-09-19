/** Proving Ground-focus Phase Hub tiles — same glass language as Birth/Awakening. */
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

export function provingGroundTilesFromLearned(
  learned: Record<string, unknown>,
): HubCharterTile[] {
  const nG = asFiniteNumber(learned.n_g);
  const gate = asFiniteNumber(learned.promotion_criteria_passed);
  return [
    {
      label: "Doel",
      value: "Rijexamen",
      tip: "Last machine exam before capital. Not walking. Not REAL money.",
      footnote: "Cert 48% · shadow · PromotionGate 4/4",
    },
    {
      label: "n_G",
      value: nG == null ? "0 / 150" : `${Math.round(nG).toLocaleString("en-US")} / 150`,
      tip: "Policy-only proving tape. Playground and Apprenticeship tapes do not count.",
      footnote: "n_G < 150 is INCONCLUSIVE",
    },
    {
      label: "Cert WR",
      value: formatPct(learned.oos_wr),
      tip: "OOS winrate on this exam. Birth certificate JSON is not pass.",
      footnote: "Need ≥ 48%",
    },
    {
      label: "Sharpe / DD",
      value: `${formatScore(learned.oos_sharpe)} / ${formatPct(learned.dd_pct)}`,
      tip: "Cert Sharpe ≥ 0.35 and peak-to-trough DD ≤ 8% of $50k MES 1-lot.",
      footnote: "Need ≥ 0.35 · ≤ 8%",
    },
    {
      label: "Shadow",
      value: yn(learned.shadow_this_run),
      tip: "This clock: live SIM fill-rate and slippage vs backtest. Audit-scan is not proof.",
      footnote: String(learned.reality_gap_band || "this run only"),
    },
    {
      label: "PromotionGate",
      value: gate == null ? "0 / 4" : `${Math.round(gate)} / 4`,
      tip: "PromotionGate.evaluate on this child. Missing evidence = reject.",
      footnote: yn(learned.promotion_this_run) === "yes" ? "this run" : "not this run",
    },
  ];
}

export function provingGroundCharterTiles(hub: MaturityHubPayload | null): HubCharterTile[] {
  return provingGroundTilesFromLearned(hub?.focus_learned ?? {});
}
