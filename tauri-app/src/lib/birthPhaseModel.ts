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
    label: "Initial DNA generation",
    headline: "Sequencing initial DNA…",
    stages: ["detected", "pipeline_boot", "checkpoint_available"],
    phases: ["detected", "checkpoint_available"],
  },
  fitness: {
    label: "Fitness landscape initialization",
    headline: "Initializing fitness landscape…",
    stages: ["loading_data", "historical_loaded", "synthetic_top_up"],
    phases: ["loading_history", "loading_history_failed", "ticks_ready", "parallel_simulation"],
  },
  strategies: {
    label: "First generation of strategies",
    headline: "Spawning first strategy generation…",
    stages: ["training_running", "parallel_simulation"],
    phases: [
      "parallel_simulation",
      "simulation_stall",
      "simulation_stall_grace",
      "simulation_stall_retry",
    ],
  },
  refinement: {
    label: "Organism refinement (PPO)",
    headline: "Refining neural policy…",
    stages: ["ppo_training"],
    phases: ["ppo_training"],
  },
  awakening: {
    label: "Neural organism online",
    headline: "Neural organism online",
    stages: ["completed", "practice_completed"],
    phases: ["completed", "practice_completed"],
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
): string {
  if (normalizeToken(status) === "completed") {
    return "Neural organism online";
  }
  const active = milestones.find((m) => m.state === "active");
  if (active) return active.headline;
  return "Organism is being born…";
}

export type BirthUiPhase = "running" | "finale" | "error" | "idle";

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
  if (payload.artifacts_ok === false) return false;
  const status = normalizeToken(payload.status);
  const stage = normalizeToken(payload.progress?.stage);
  return status === "completed" || stage === "completed" || stage === "practice_completed";
}

export function isBirthRunning(payload: BirthStatusPayload): boolean {
  const status = normalizeToken(payload.status);
  return status === "running" || status === "started";
}

export function isBirthFailed(payload: BirthStatusPayload): boolean {
  const status = normalizeToken(payload.status);
  return status === "error" || status === "interrupted";
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
