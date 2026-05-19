import type { PPOEvolutionMetric } from "@/lib/ppoEvolutionTypes";

export type EvolutionEventType =
  | "reward_spike"
  | "entropy_dip"
  | "winrate_surge"
  | "explained_variance_drop";

export interface EvolutionTimelineEvent {
  type: EvolutionEventType;
  label: string;
}

export interface EvolutionTimelineEntry {
  step: number;
  meanReward: number;
  winrate: number;
  entropy: number;
  events: EvolutionTimelineEvent[];
}

export const DEFAULT_TIMELINE_MAX_STEPS = 50;

const EVENT_LABELS: Record<EvolutionEventType, string> = {
  reward_spike: "Reward spike",
  entropy_dip: "Entropy dip",
  winrate_surge: "Winrate surge",
  explained_variance_drop: "Value fit drop",
};

function detectEvents(
  current: PPOEvolutionMetric,
  previous: PPOEvolutionMetric,
): EvolutionTimelineEvent[] {
  const events: EvolutionTimelineEvent[] = [];

  const rewardDelta = current.mean_reward - previous.mean_reward;
  const rewardThreshold = Math.max(0.08, Math.abs(previous.mean_reward) * 0.15);
  if (rewardDelta >= rewardThreshold) {
    events.push({ type: "reward_spike", label: EVENT_LABELS.reward_spike });
  }

  const entropyDelta = current.entropy - previous.entropy;
  if (entropyDelta <= -0.12) {
    events.push({ type: "entropy_dip", label: EVENT_LABELS.entropy_dip });
  }

  const winrateDelta = current.winrate_rolling_5k - previous.winrate_rolling_5k;
  if (winrateDelta >= 0.05) {
    events.push({ type: "winrate_surge", label: EVENT_LABELS.winrate_surge });
  }

  const explainedVarianceDelta = current.explained_variance - previous.explained_variance;
  if (explainedVarianceDelta <= -0.15) {
    events.push({
      type: "explained_variance_drop",
      label: EVENT_LABELS.explained_variance_drop,
    });
  }

  return events;
}

function toTimelineEntry(metric: PPOEvolutionMetric, events: EvolutionTimelineEvent[]): EvolutionTimelineEntry {
  return {
    step: metric.step,
    meanReward: metric.mean_reward,
    winrate: metric.winrate_rolling_5k,
    entropy: metric.entropy,
    events,
  };
}

export function buildEvolutionTimeline(
  logs: PPOEvolutionMetric[],
  maxSteps = DEFAULT_TIMELINE_MAX_STEPS,
): EvolutionTimelineEntry[] {
  const slice = logs.slice(-maxSteps);

  return slice.map((metric, index) => {
    if (index === 0) {
      return toTimelineEntry(metric, []);
    }
    return toTimelineEntry(metric, detectEvents(metric, slice[index - 1]!));
  });
}
