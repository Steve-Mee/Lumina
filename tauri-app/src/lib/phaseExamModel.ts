import type { MaturityHubPayload } from "@/lib/maturationClient";

export interface PhaseExamModel {
  goal: string;
  progressLine: string;
  performanceLabel: string;
  performanceLine: string;
  attemptLine: string | null;
  blockers: string[];
}

const DISCARD_PLAIN: Record<string, string> = {
  occupancy_out_of_band: "Discarded: occupancy outside 25–75%.",
  stable_rank_drop: "Discarded: risk shape fell below the incumbent.",
  skill_regression: "Discarded: win rate and mean R both fell.",
  evolution_wall_lost: "Discarded: the evolution-proof wall was lost.",
  overhold_volume_down: "Discarded: hold longer than geometry with less volume.",
  no_prefer_better: "Discarded: no prefer-better improvement.",
};

function asNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim() !== "") {
    const n = Number(value);
    return Number.isFinite(n) ? n : null;
  }
  return null;
}

function asText(value: unknown, fallback = "—"): string {
  if (typeof value === "string" && value.trim()) return value.trim();
  if (typeof value === "number" && Number.isFinite(value)) return String(value);
  return fallback;
}

function fmtR(value: unknown): string {
  const n = asNumber(value);
  if (n == null) return "—";
  return n.toFixed(3);
}

function fmtPct(value: unknown): string {
  const n = asNumber(value);
  if (n == null) return "—";
  const ratio = Math.abs(n) <= 1.5 ? n : n / 100;
  return `${(ratio * 100).toFixed(1)}%`;
}

function fmtCount(value: unknown): string {
  const n = asNumber(value);
  if (n == null) return "—";
  return Math.round(n).toLocaleString("en-US");
}

export function discardPlain(reason: unknown): string | null {
  if (typeof reason !== "string" || !reason.trim()) return null;
  return DISCARD_PLAIN[reason] ?? reason;
}

function goalFor(hub: MaturityHubPayload | null, phaseId: string, fallback: string): string {
  const spec = hub?.phase_specs?.[phaseId];
  const goal = spec?.human_goal?.trim();
  return goal || fallback;
}

function blockerLine(missing: unknown): string[] {
  if (!Array.isArray(missing)) return [];
  return missing.map((item) => String(item)).filter((item) => item.trim()).slice(0, 6);
}

export function buildAwakeningExam(input: {
  hub: MaturityHubPayload | null;
  learned: Record<string, unknown>;
  running: boolean;
  missing?: string[];
  progressMessage?: string | null;
}): PhaseExamModel {
  const learned = input.learned;
  const activity = asText(learned.activity, input.running ? "eval B" : "idle");
  const nB = asNumber(learned.n_b);
  const progressLine = [
    "First Watch",
    "no learn",
    activity,
    `n_B ${nB == null ? "—" : fmtCount(nB)}/500`,
    input.progressMessage?.trim() || "",
  ]
    .filter(Boolean)
    .join(" · ");
  const performanceLine = [
    `mean R ${fmtR(learned.mean_r)}`,
    `WR ${fmtPct(learned.wr)}`,
    `flat ${fmtPct(learned.occupancy)}`,
    asText(learned.stable_class, "INCONCLUSIVE"),
  ].join(" · ");
  const lastN = asNumber(learned.last_shot_n_b);
  const reason = discardPlain(learned.discard_reason);
  const attemptLine =
    lastN == null
      ? null
      : [
          `Last shot n ${fmtCount(lastN)}`,
          `mean R ${fmtR(learned.last_shot_mean_r)}`,
          `flat ${fmtPct(learned.last_shot_occupancy)}`,
          asText(learned.last_shot_stable_class),
          reason ?? "",
        ]
          .filter(Boolean)
          .join(" · ");
  return {
    goal: goalFor(
      input.hub,
      "awakening",
      "First Watch: frozen Birth plant on holdout B. No learn(). STABLE + n_B≥500.",
    ),
    progressLine,
    performanceLabel: "Holdout B, policy closes only",
    performanceLine,
    attemptLine,
    blockers: blockerLine(input.missing),
  };
}

export function buildPhaseExam(input: {
  phaseId: string;
  hub: MaturityHubPayload | null;
  learned: Record<string, unknown>;
  running: boolean;
  missing?: string[];
  progressMessage?: string | null;
  performanceLabel: string;
  fallbackGoal: string;
}): PhaseExamModel {
  const learned = input.learned;
  const activity = asText(learned.activity, input.running ? "running" : "idle");
  const message = input.progressMessage?.trim() || "";
  const bits = [
    `mean R ${fmtR(learned.mean_r)}`,
    learned.wr != null ? `WR ${fmtPct(learned.wr)}` : "",
    learned.sharpe != null ? `Sharpe ${fmtR(learned.sharpe)}` : "",
    learned.dd_pct != null ? `DD ${fmtPct(learned.dd_pct)}` : "",
  ].filter(Boolean);
  return {
    goal: goalFor(input.hub, input.phaseId, input.fallbackGoal),
    progressLine: [activity, message].filter(Boolean).join(" · ") || "—",
    performanceLabel: input.performanceLabel,
    performanceLine: bits.length > 0 ? bits.join(" · ") : "—",
    attemptLine: null,
    blockers: blockerLine(input.missing),
  };
}
