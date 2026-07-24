import type { BirthProgressPayload, BirthStatusPayload } from "@/lib/birthClient";

import { isBirthCertificateFailed } from "@/lib/birth/birthStatusPredicates";
import { normalizeToken } from "@/lib/birth/birthModelUtils";


export type BirthMilestoneId = "dna" | "fitness" | "strategies" | "refinement" | "awakening";

export type MilestoneState = "pending" | "active" | "complete";

export interface BirthMilestone {
  id: BirthMilestoneId;
  label: string;
  headline: string;
  state: MilestoneState;
}

export const BIRTH_MILESTONE_ORDER: BirthMilestoneId[] = [
  "dna",
  "fitness",
  "strategies",
  "refinement",
  "awakening",
];

const MILESTONE_META: Record<
  BirthMilestoneId,
  { label: string; headline: string; stages: string[]; phases: string[] }
> = {
  dna: {
    label: "Real market history",
    headline: "Loading real market history…",
    stages: ["detected", "pipeline_boot", "checkpoint_available"],
    phases: ["detected", "checkpoint_available", "loading_history"],
  },
  fitness: {
    label: "Regime map",
    headline: "Building regime map…",
    stages: ["loading_data", "historical_loaded", "synthetic_top_up"],
    phases: [
      "loading_history",
      "loading_history_failed",
      "enriching_news",
      "enriching_regimes",
      "train_holdout_split",
      "holdout_preflight",
      "holdout_preflight_expansion",
      "policy_init",
      "ticks_ready",
    ],
  },
  strategies: {
    label: "Curriculum training",
    headline: "Curriculum stage active…",
    stages: ["training_running"],
    phases: [
      "curriculum_stage",
      "curriculum_learning",
      "curriculum_research",
      "data_expansion",
      "parallel_simulation",
      "ppo_training",
    ],
  },
  refinement: {
    label: "PPO polish + OOS eval",
    headline: "Policy polish and OOS Sharpe check…",
    stages: ["ppo_training"],
    phases: ["ppo_polish", "oos_evaluation"],
  },
  awakening: {
    label: "Birth Certificate v2",
    headline: "Birth Certificate v2 issued",
    stages: ["completed", "practice_completed"],
    phases: ["completed", "practice_completed", "certificate_issued"],
  },
};

export function resolveActiveMilestone(
  progress: BirthProgressPayload | undefined,
  status: string,
): BirthMilestoneId {
  const stage = normalizeToken(progress?.stage);
  const phase = normalizeToken(progress?.phase);
  const normalizedStatus = normalizeToken(status);

  if (normalizedStatus === "completed" || stage === "completed" || stage === "practice_completed") {
    return "awakening";
  }

  if (
    phase === "loading_history" ||
    stage === "detected" ||
    stage === "pipeline_boot" ||
    stage === "checkpoint_available"
  ) {
    return "dna";
  }

  if (
    phase === "enriching_news" ||
    phase === "enriching_regimes" ||
    phase === "train_holdout_split" ||
    phase === "holdout_preflight" ||
    phase === "holdout_preflight_expansion" ||
    phase === "policy_init"
  ) {
    return "fitness";
  }

  for (let i = BIRTH_MILESTONE_ORDER.length - 1; i >= 0; i -= 1) {
    const id = BIRTH_MILESTONE_ORDER[i]!;
    const meta = MILESTONE_META[id];
    if (meta.stages.includes(stage) || meta.phases.includes(phase)) {
      return id;
    }
  }

  if (phase === "ppo_polish" || phase === "oos_evaluation") return "refinement";
  if (phase === "ppo_training") return "strategies";
  if (phase.includes("simulation") || stage.includes("simulation") || stage.includes("training")) {
    return "strategies";
  }
  if (phase.includes("loading") || stage.includes("loading") || stage.includes("historical")) {
    return stage === "historical_loaded" || phase === "ticks_ready" ? "fitness" : "dna";
  }

  return "dna";
}

export function buildMilestones(
  progress: BirthProgressPayload | undefined,
  status: string,
): BirthMilestone[] {
  const activeId = resolveActiveMilestone(progress, status);
  const activeIndex = BIRTH_MILESTONE_ORDER.indexOf(activeId);

  return BIRTH_MILESTONE_ORDER.map((id, index) => {
    let state: MilestoneState = "pending";
    if (index < activeIndex) state = "complete";
    else if (index === activeIndex) state = "active";
    const meta = MILESTONE_META[id];
    return {
      id,
      label: meta.label,
      headline: meta.headline,
      state,
    };
  });
}

export interface CompactMilestoneView {
  items: BirthMilestone[];
  upcomingCount: number;
}

/** Show completed + active + next milestone only (max 3 visible). Drawer / dense surfaces. */
export function buildCompactMilestones(
  progress: BirthProgressPayload | undefined,
  status: string,
): CompactMilestoneView {
  const all = buildMilestones(progress, status);
  const activeIndex = all.findIndex((m) => m.state === "active");
  if (activeIndex < 0) {
    return { items: all.slice(0, 1), upcomingCount: Math.max(0, all.length - 1) };
  }
  const start = Math.max(0, activeIndex - 1);
  const end = Math.min(all.length, activeIndex + 2);
  const items = all.slice(start, end);
  const upcomingCount = Math.max(0, all.length - end);
  return { items, upcomingCount };
}

/**
 * Mission HUD rail: previous complete + active + all remaining as chips.
 * Never collapses tail into a "+N" counter — room exists for full labels.
 */
export function buildHudMilestones(
  progress: BirthProgressPayload | undefined,
  status: string,
): CompactMilestoneView {
  const all = buildMilestones(progress, status);
  const activeIndex = all.findIndex((m) => m.state === "active");
  if (activeIndex < 0) {
    return { items: all, upcomingCount: 0 };
  }
  const start = Math.max(0, activeIndex - 1);
  return { items: all.slice(start), upcomingCount: 0 };
}

export function resolveBirthHeadline(
  milestones: BirthMilestone[],
  status: string,
  progress?: BirthProgressPayload,
  certificateOk?: boolean,
): string {
  const failedPayload: BirthStatusPayload = {
    status,
    progress,
    certificate_ok: certificateOk,
  };
  if (isBirthCertificateFailed(failedPayload)) {
    if (normalizeToken(status) === "certificate_failed" || progress?.phase === "certificate_failed") {
      return "Birth Certificate thresholds not met";
    }
    return "Birth Certificate v2 required";
  }
  if (normalizeToken(status) === "completed") {
    return "Birth Certificate v2 issued";
  }
  if (normalizeToken(status) === "certificate_failed") {
    return "Birth Certificate thresholds not met — review OOS metrics and retry";
  }
  const phase = normalizeToken(progress?.phase);
  if (
    phase === "loading_history" ||
    phase === "enriching_news" ||
    phase === "enriching_regimes" ||
    phase === "train_holdout_split" ||
    phase === "holdout_preflight" ||
    phase === "holdout_preflight_expansion" ||
    phase === "policy_init"
  ) {
    const msg = String(progress?.message ?? "").trim();
    if (msg) {
      return msg;
    }
    if (phase === "loading_history") {
      const chunk = Number(
        (progress as Record<string, unknown> | undefined)?.loading_chunk ??
          (progress as Record<string, unknown> | undefined)?.chunk_index ??
          0,
      );
      const total = Number(progress?.chunk_total ?? 0);
      if (chunk > 0 && total > 0) {
        return `Loading real history (${chunk}/${total} chunks)…`;
      }
      return "Loading real market history…";
    }
    if (phase === "enriching_regimes") {
      return "Building regime map…";
    }
    return "Preparing birth training data…";
  }
  if (phase === "oos_evaluation") {
    const sharpe = Number(progress?.oos_metrics?.oos_sharpe ?? 0);
    return `OOS Sharpe evaluation (${sharpe.toFixed(2)})…`;
  }
  const curriculum = String(progress?.curriculum_stage ?? "").trim();
  if (curriculum) {
    return `Curriculum ${curriculum.replace(/_/g, " ")}…`;
  }
  const days = Number(progress?.actual_real_days_loaded ?? 0);
  if (days > 0 && phase.includes("loading")) {
    return `Loading real history (${days} days)…`;
  }
  const active = milestones.find((m) => m.state === "active");
  if (active) return active.headline;
  return "Birth Phase v2 in progress…";
}

import type { BirthUiPhase } from "@/lib/birth/birthClientTypes";
export type { BirthUiPhase };

export function resolveBirthPhaseCopy(
  uiPhase: BirthUiPhase,
  milestones: BirthMilestone[],
): string {
  if (uiPhase === "finale") {
    return "Birth phase complete — continue training or enter the command deck.";
  }
  if (uiPhase === "error") {
    return "Birth interrupted — review diagnostics or retry.";
  }
  if (uiPhase === "certificate_failed") {
    return "Certificate thresholds not met — review OOS metrics below and retry birth.";
  }
  if (uiPhase === "stage_stalled") {
    return "Curriculum stage stalled — review the blocker and choose a recovery action.";
  }
  const active = milestones.find((m) => m.state === "active");
  if (active?.id === "refinement") {
    return "Policy refinement in progress — neural lattice stabilizing.";
  }
  if (active?.id === "strategies") {
    return "Strategy generation active — parallel simulation lanes open.";
  }
  if (active?.id === "fitness") {
    return "Fitness landscape loading — historical and synthetic lanes merging.";
  }
  if (active?.id === "dna") {
    return "Real market history loading — preflight and tick cache warming.";
  }
  return "Neural lattice forming — DNA, strategies, and policy in parallel.";
}
