import type { BirthProgressPayload, BirthStatusPayload } from "@/lib/birthClient";

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
    phases: ["loading_history", "loading_history_failed", "ticks_ready"],
  },
  strategies: {
    label: "Curriculum training",
    headline: "Curriculum stage active…",
    stages: ["training_running"],
    phases: ["curriculum_stage", "parallel_simulation"],
  },
  refinement: {
    label: "PPO polish + OOS eval",
    headline: "Policy polish and OOS Sharpe check…",
    stages: ["ppo_training"],
    phases: ["ppo_training", "ppo_polish", "oos_evaluation"],
  },
  awakening: {
    label: "Birth Certificate v2",
    headline: "Birth Certificate v2 issued",
    stages: ["completed", "practice_completed"],
    phases: ["completed", "practice_completed", "certificate_issued"],
  },
};

function normalizeToken(value: unknown): string {
  return String(value ?? "")
    .trim()
    .toLowerCase();
}

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

  for (let i = BIRTH_MILESTONE_ORDER.length - 1; i >= 0; i -= 1) {
    const id = BIRTH_MILESTONE_ORDER[i]!;
    const meta = MILESTONE_META[id];
    if (meta.stages.includes(stage) || meta.phases.includes(phase)) {
      return id;
    }
  }

  if (phase.includes("ppo") || stage.includes("ppo")) return "refinement";
  if (phase.includes("simulation") || stage.includes("simulation") || stage.includes("training")) {
    return "strategies";
  }
  if (phase.includes("loading") || stage.includes("loading") || stage.includes("historical")) {
    return "fitness";
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

export function resolveBirthHeadline(
  milestones: BirthMilestone[],
  status: string,
  progress?: BirthProgressPayload,
): string {
  if (normalizeToken(status) === "completed") {
    return "Birth Certificate v2 issued";
  }
  if (normalizeToken(status) === "certificate_failed") {
    return "Birth Certificate thresholds not met — review OOS metrics and retry";
  }
  const phase = normalizeToken(progress?.phase);
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

export type BirthUiPhase = "running" | "finale" | "error" | "idle" | "certificate_failed";

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
  return "Neural lattice forming — DNA, strategies, and policy in parallel.";
}

export function isBirthComplete(payload: BirthStatusPayload): boolean {
  if (payload.certificate_ok === false || payload.artifacts_ok === false) return false;
  const status = normalizeToken(payload.status);
  const stage = normalizeToken(payload.progress?.stage);
  const phase = normalizeToken(payload.progress?.phase);
  return (
    status === "completed" ||
    stage === "completed" ||
    stage === "practice_completed" ||
    phase === "certificate_issued"
  );
}

export function isBirthRunning(payload: BirthStatusPayload): boolean {
  const status = normalizeToken(payload.status);
  return status === "running" || status === "started" || status === "active";
}

export function isBirthInterrupted(payload: BirthStatusPayload): boolean {
  const status = normalizeToken(payload.status);
  const stage = normalizeToken(payload.progress?.stage);
  return status === "interrupted" || stage === "interrupted";
}

export function isBirthCertificateFailed(payload: BirthStatusPayload): boolean {
  const status = normalizeToken(payload.status);
  const stage = normalizeToken(payload.progress?.stage);
  const phase = normalizeToken(payload.progress?.phase);
  return (
    status === "certificate_failed" ||
    (stage === "failed" && phase === "certificate_failed") ||
    payload.certificate_ok === false
  );
}

export function isBirthFailed(payload: BirthStatusPayload): boolean {
  const status = normalizeToken(payload.status);
  return status === "error" || status === "certificate_failed";
}

export function extractSimProgress(progress: BirthProgressPayload | undefined): {
  done: number;
  target: number;
  pct: number;
} {
  const done = Number(
    progress?.trades_done ?? progress?.cumulative_trades ?? progress?.total_trades ?? 0,
  );
  const target = Number(progress?.target_trades ?? 0);
  const pct =
    target > 0
      ? Math.min(100, (done / target) * 100)
      : Number(progress?.progress_pct ?? 0);
  return { done, target, pct };
}

export function extractPpoProgress(progress: BirthProgressPayload | undefined): {
  steps: number;
  label: string;
} {
  const steps = Number(
    progress?.ppo_steps_cumulative ?? progress?.ppo_steps ?? 0,
  );
  const batch = Number(progress?.ppo_batch_count ?? 0);
  const label =
    batch > 0 ? `${steps.toLocaleString()} steps · batch ${batch}` : `${steps.toLocaleString()} steps`;
  return { steps, label };
}
