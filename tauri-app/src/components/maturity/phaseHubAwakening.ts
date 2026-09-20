/** Awakening-focus Phase Hub tiles — same glass language as Birth, different KPIs. */
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

function formatCount(value: unknown): string {
  const n = asFiniteNumber(value);
  if (n == null) return "—";
  return Math.round(n).toLocaleString("en-US");
}

export function awakeningTilesFromLearned(
  learned: Record<string, unknown>,
): HubCharterTile[] {
  const nB = asFiniteNumber(learned.n_b);
  const lift = asFiniteNumber(learned.lift);
  const sign = lift != null && lift >= 0 ? "+" : "";
  const stable = typeof learned.stable_class === "string" ? learned.stable_class : "INCONCLUSIVE";
  return [
    {
      label: "Doel",
      value: "Ogen open",
      tip: "Prefer a better child than frozen Birth π*. Not a WR exam. Not REAL.",
      footnote: "Prefer-better · regimes · recover",
    },
    {
      label: "n_B",
      value: nB == null ? "0 / 500" : `${Math.round(nB).toLocaleString("en-US")} / 500`,
      tip: "Policy-only holdout closes. n_B < 500 is INCONCLUSIVE, never a pass.",
      footnote: nBFootnote(learned),
    },
    {
      label: "Lift vs Birth",
      value: lift == null ? "—" : `${sign}${formatPct(lift)}`,
      tip: "Child OOS minus cycle-0 parent on the same exam. Necessary with occupancy/STABLE, not sufficient alone.",
      footnote: `Birth ${formatPct(learned.birth_oos_wr)} → child ${formatPct(learned.wr)}`,
    },
    {
      label: "Occupancy",
      value: formatPct(learned.occupancy),
      tip: "Exam band 25–75% plant-flat. Same physics as Birth S3–S5.",
      footnote: "25–75% exam band",
    },
    {
      label: "STABLE",
      value: stable,
      tip: "Sharpe > −2 and DD ≤ 25% of $50k MES 1-lot. REGRESS or INCONCLUSIVE is not a pass.",
      footnote: "Grind classifier · not a WR stamp",
    },
    {
      label: "Twin watch",
      value: formatCount(learned.twin_watch_n),
      tip: "Observations of THIS Awakening run. A metrics dump of 197k samples is not proof.",
      footnote: "Twin-source events of this run only",
    },
  ];
}

function nBFootnote(learned: Record<string, unknown>): string {
  const examKind = typeof learned.exam_kind === "string" ? learned.exam_kind : "";
  const examN = asFiniteNumber(learned.exam_n);
  const examBit =
    examKind === "holdout_B_plus_continuation"
      ? examN != null
        ? `Exam B+later OOS · ${Math.round(examN).toLocaleString("en-US")} ticks`
        : "Exam B+later OOS · same physics"
      : "";
  const kept = learned.kept;
  const last = asFiniteNumber(learned.last_shot_n_b ?? learned.discarded_n_b);
  if (kept === false && last != null) {
    return examBit
      ? `${examBit} · last shot ${Math.round(last)} discarded`
      : `Last shot ${Math.round(last)} discarded · incumbent kept`;
  }
  if (kept === true) {
    return examBit ? `${examBit} · child kept` : "Child kept · next cycle continues this zip";
  }
  const cycle = asFiniteNumber(learned.cycle);
  if (examBit) {
    return examBit;
  }
  if (cycle != null) {
    return `Cycle ${Math.round(cycle)} · skill clock · no effective_min cheat`;
  }
  return "Skill clock · no effective_min cheat";
}

export function awakeningCharterTiles(hub: MaturityHubPayload | null): HubCharterTile[] {
  return awakeningTilesFromLearned(hub?.focus_learned ?? {});
}
