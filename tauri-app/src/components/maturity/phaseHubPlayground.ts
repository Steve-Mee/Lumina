/** Playground-focus Phase Hub tiles — same glass language as Birth/Awakening. */
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

export function playgroundTilesFromLearned(
  learned: Record<string, unknown>,
): HubCharterTile[] {
  const nP = asFiniteNumber(learned.n_p);
  return [
    {
      label: "Doel",
      value: "Eerste stappen",
      tip: "Crawl in NinjaTrader SIM with fictional capital. Not a Birth WR exam. Not REAL.",
      footnote: "First fill · WR ≥ BE · mean R ≥ 0",
    },
    {
      label: "First fill",
      value: yn(learned.first_fill),
      tip: "Venue fill via the order path. JSON stamps and health flags do not count.",
      footnote: String(learned.first_fill_source || "orderpath only"),
    },
    {
      label: "n_P",
      value: nP == null ? "0 / 150" : `${Math.round(nP).toLocaleString("en-US")} / 150`,
      tip: "Policy-only SIM closes. n_P < 150 is INCONCLUSIVE, never a pass.",
      footnote: "Skill clock · no JSON cheat",
    },
    {
      label: "WR vs BE",
      value: `${formatPct(learned.skill_wr)} / ${formatPct(learned.breakeven_wr)}`,
      tip: "Skill WR must meet live geometry breakeven on this SIM tape, not Birth fitness.",
      footnote: "Playground tape · policy-only",
    },
    {
      label: "Mean R",
      value: formatScore(learned.mean_r),
      tip: "Mean R ≥ 0 on playground policy closes. Birth mean R is a baseline, not a pass.",
      footnote: "Economic viability AND",
    },
    {
      label: "Envelope",
      value: yn(learned.envelope_sealed),
      tip: "Operator-sealed SIM risk envelope. Missing file is unsealed. Breach is a fail.",
      footnote: learned.envelope_breached === true ? "breached" : "fictional capital",
    },
  ];
}

export function playgroundCharterTiles(hub: MaturityHubPayload | null): HubCharterTile[] {
  return playgroundTilesFromLearned(hub?.focus_learned ?? {});
}
