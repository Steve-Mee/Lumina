import type { PPOEvolutionMetric } from "@/lib/ppoEvolutionTypes";

export type RegimeLabel = "trending_up" | "trending_down" | "ranging" | "high_volatility";

export interface RegimeHeatmapCell {
  regime: RegimeLabel;
  displayName: string;
  sampleCount: number;
  avgReward: number;
  intensity: number;
}

const REGIME_ORDER: RegimeLabel[] = [
  "trending_up",
  "trending_down",
  "ranging",
  "high_volatility",
];

const REGIME_DISPLAY: Record<RegimeLabel, string> = {
  trending_up: "Trending Up",
  trending_down: "Trending Down",
  ranging: "Ranging",
  high_volatility: "High Volatility",
};

function inferRegime(
  metric: PPOEvolutionMetric,
  previous: PPOEvolutionMetric | null,
): RegimeLabel {
  if (metric.entropy > 1.2 || metric.policy_loss > 0.12) {
    return "high_volatility";
  }

  const rewardDelta = previous ? metric.mean_reward - previous.mean_reward : 0;
  const { long, short } = metric.action_distribution;

  if (rewardDelta > 0.05 && long > short) return "trending_up";
  if (rewardDelta < -0.05 && short > long) return "trending_down";
  return "ranging";
}

function clamp01(value: number): number {
  return Math.min(1, Math.max(0, value));
}

export function buildRegimeHeatmap(logs: PPOEvolutionMetric[]): RegimeHeatmapCell[] {
  const buckets = new Map<RegimeLabel, number[]>();

  for (const regime of REGIME_ORDER) {
    buckets.set(regime, []);
  }

  logs.forEach((metric, index) => {
    const previous = index > 0 ? logs[index - 1]! : null;
    const regime = inferRegime(metric, previous);
    buckets.get(regime)!.push(metric.mean_reward);
  });

  const avgRewards = REGIME_ORDER.map((regime) => {
    const rewards = buckets.get(regime)!;
    const avgReward =
      rewards.length > 0 ? rewards.reduce((sum, value) => sum + value, 0) / rewards.length : 0;
    return { regime, avgReward, sampleCount: rewards.length };
  });

  const nonZeroRewards = avgRewards
    .filter((entry) => entry.sampleCount > 0)
    .map((entry) => entry.avgReward);
  const minReward = nonZeroRewards.length > 0 ? Math.min(...nonZeroRewards) : 0;
  const maxReward = nonZeroRewards.length > 0 ? Math.max(...nonZeroRewards) : 1;
  const range = Math.max(maxReward - minReward, 0.01);

  return REGIME_ORDER.map((regime) => {
    const entry = avgRewards.find((item) => item.regime === regime)!;
    const intensity =
      entry.sampleCount === 0
        ? 0
        : clamp01((entry.avgReward - minReward) / range);

    return {
      regime,
      displayName: REGIME_DISPLAY[regime],
      sampleCount: entry.sampleCount,
      avgReward: entry.avgReward,
      intensity,
    };
  });
}
