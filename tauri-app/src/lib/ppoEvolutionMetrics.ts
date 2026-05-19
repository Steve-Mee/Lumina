import type { PPOEvolutionMetric } from "@/lib/ppoEvolutionTypes";

export function clamp01(value: number): number {
  return Math.min(1, Math.max(0, value));
}

export function normalizeMeanReward(
  reward: number,
  logs: PPOEvolutionMetric[],
): number {
  const maxAbs = Math.max(0.01, ...logs.map((entry) => Math.abs(entry.mean_reward)));
  return clamp01((reward / maxAbs + 1) / 2);
}

export function normalizeEntropy(entropy: number): number {
  return clamp01(entropy / 2);
}

export function normalizeExplainedVariance(explainedVariance: number): number {
  return clamp01(explainedVariance);
}

export function normalizeWinrate(winrate: number): number {
  return clamp01(winrate);
}

export function gaugePercent(value: number): number {
  return Math.round(clamp01(value) * 100);
}
