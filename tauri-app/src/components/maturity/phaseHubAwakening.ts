/** Awakening-focus Phase Hub tiles — First Watch KPIs, not child-beats-parent. */
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

function plantValue(learned: Record<string, unknown>): string {
  const child = typeof learned.child_weight_sha === "string" ? learned.child_weight_sha : "";
  const init = typeof learned.init_weight_sha === "string" ? learned.init_weight_sha : "";
  if (!child || !init) return "—";
  return child === init ? "plant" : "not plant";
}

function constitutionValue(learned: Record<string, unknown>): string {
  const violations = asFiniteNumber(learned.constitution_violations);
  const blocks = asFiniteNumber(learned.constitution_blocks);
  if (violations == null || blocks == null) return "—";
  if (violations === 0 && blocks === 0) return "clear";
  return `${Math.round(violations)} / ${Math.round(blocks)}`;
}

export function awakeningTilesFromLearned(
  learned: Record<string, unknown>,
): HubCharterTile[] {
  const nB = asFiniteNumber(learned.n_b);
  const stable = typeof learned.stable_class === "string" ? learned.stable_class : "INCONCLUSIVE";
  const plant = plantValue(learned);
  return [
    {
      label: "Goal",
      value: "First Watch",
      tip: "One blind holdout-B eval of the frozen Birth plant. No learn(). Not a WR exam. Not REAL.",
      footnote: "Plant baseline · STABLE · constitution 0",
    },
    {
      label: "n_B",
      value: nB == null ? "— / 500" : `${Math.round(nB).toLocaleString("en-US")} / 500`,
      tip: "Policy-only holdout closes. n_B < 500 is INCONCLUSIVE, never a pass.",
      footnote: nBFootnote(learned),
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
      label: "Plant",
      value: plant,
      tip: "Weight sha must equal the frozen Birth plant. A different sha is baseline_not_the_plant.",
      footnote: plant === "plant" ? "Birth weight sha" : "Must be the Birth plant",
    },
    {
      label: "Constitution",
      value: constitutionValue(learned),
      tip: "Rollout-guard violations and blocks must both be zero. Unmeasured stays fail-closed.",
      footnote: "0 violations · 0 blocks",
    },
  ];
}

function nBFootnote(learned: Record<string, unknown>): string {
  const activity =
    typeof learned.activity === "string" && learned.activity.trim()
      ? learned.activity.trim().replace(/_/g, " ")
      : "";
  if (activity) return `${activity} · policy-only holdout · no learn`;
  return "Policy-only holdout · no learn";
}

export function awakeningCharterTiles(hub: MaturityHubPayload | null): HubCharterTile[] {
  return awakeningTilesFromLearned(hub?.focus_learned ?? {});
}

/** Hero clock for the one-screen Awakening instrument. Volume is the bar, not a pass. */
export function awakeningSkillClock(learned: Record<string, unknown>): {
  nB: number;
  nBLabel: string;
  pct: number;
  activity: string;
} {
  const nB = asFiniteNumber(learned.n_b);
  const activity =
    typeof learned.activity === "string" && learned.activity.trim()
      ? learned.activity.trim()
      : "idle";
  const rounded = nB == null ? 0 : Math.max(0, Math.round(nB));
  return {
    nB: rounded,
    nBLabel: rounded.toLocaleString("en-US"),
    pct: Math.max(0, Math.min(100, (rounded / 500) * 100)),
    activity,
  };
}

export function awakeningNumber(value: unknown): number | null {
  return asFiniteNumber(value);
}

export function formatAwakeningFixed(value: unknown, digits = 2): string {
  const n = asFiniteNumber(value);
  return n == null ? "—" : n.toFixed(digits);
}

export function formatAwakeningPct(value: unknown): string {
  const n = asFiniteNumber(value);
  if (n == null) return "—";
  const ratio = Math.abs(n) <= 1.5 ? n : n / 100;
  return `${(ratio * 100).toFixed(1)}%`;
}

export function occupancyChipLabel(value: unknown): string {
  const n = asFiniteNumber(value);
  if (n == null) return "occ —";
  const pct = Math.abs(n) <= 1.5 ? n * 100 : n;
  return `occ ${Math.round(pct)}%`;
}

export function awakeningStableTone(value: string): "default" | "success" | "warn" {
  const token = value.toUpperCase();
  if (token.includes("REGRESS") || token.includes("INCONCLUSIVE")) return "warn";
  if (token === "—" || token === "") return "default";
  return "success";
}
