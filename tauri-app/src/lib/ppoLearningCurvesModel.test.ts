import { describe, expect, it } from "vitest";

import { mapLogsToLearningCurvePoints } from "@/lib/ppoLearningCurvesModel";
import type { PPOEvolutionMetric } from "@/lib/ppoEvolutionTypes";

function metric(overrides: Partial<PPOEvolutionMetric> = {}): PPOEvolutionMetric {
  return {
    timestamp: "2026-01-01T00:00:00Z",
    step: 5000,
    mean_reward: 0.5,
    policy_loss: 0.1,
    value_loss: 0.2,
    entropy: 1.0,
    explained_variance: 0.8,
    winrate_rolling_5k: 0.55,
    sharpe_rolling_5k: 1.2,
    action_distribution: { long: 0.4, short: 0.3, hold: 0.3 },
    avg_stop_pct: 0.01,
    avg_target_pct: 0.02,
    ...overrides,
  };
}

describe("ppoLearningCurvesModel", () => {
  it("maps logs to mean reward and entropy chart points", () => {
    const logs = [
      metric({ step: 5000, mean_reward: 0.2, entropy: 0.8 }),
      metric({ step: 10000, mean_reward: 0.6, entropy: 1.1 }),
    ];

    expect(mapLogsToLearningCurvePoints(logs)).toEqual([
      { step: 5000, meanReward: 0.2, entropy: 0.8 },
      { step: 10000, meanReward: 0.6, entropy: 1.1 },
    ]);
  });
});
