import type { PPOEvolutionMetric } from "@/lib/ppoEvolutionTypes";

export interface LearningCurvePoint {
  step: number;
  meanReward: number;
  entropy: number;
}

export function mapLogsToLearningCurvePoints(logs: PPOEvolutionMetric[]): LearningCurvePoint[] {
  return logs.map((metric) => ({
    step: metric.step,
    meanReward: metric.mean_reward,
    entropy: metric.entropy,
  }));
}
