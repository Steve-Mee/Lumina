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
  const green = asFiniteNumber(learned.green_days);
  return [
    {
      label: "Doel",
      value: "Leerschool",
      tip: "Zij probeert op SIM. Een 240-minutenkaars is geen startsein. Geen REAL.",
      footnote: "Poort: 5 groene sessiedagen",
    },
    {
      label: "Groene dagen",
      value: `${Math.round(green ?? 0)} / 5`,
      tip: "Aaneengesloten sessiedagen met een echte fill en verwachting boven 0. Een bijvul is geen dag.",
      footnote: "Vrijdag naar maandag telt",
    },
    {
      label: "Closes",
      value: nP == null ? "0" : Math.round(nP).toLocaleString("en-US"),
      tip: "Echte policy-closes. Dit getal is geen poort van 150.",
      footnote: "150 closes is het examen in Apprenticeship",
    },
    {
      label: "WR vs BE",
      value: `${formatPct(learned.skill_wr)} / ${formatPct(learned.breakeven_wr)}`,
      tip: "Meting. Zonder closes is er geen breakeven. Dit is niet de schoolpoort.",
      footnote: "De poort WR ≥ BE zit in Apprenticeship",
    },
    {
      label: "Mean R",
      value: formatScore(learned.mean_r),
      tip: "Meting op policy-closes. Geen schoolpoort.",
      footnote: "Mean R ≥ 0 zit in Apprenticeship",
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
