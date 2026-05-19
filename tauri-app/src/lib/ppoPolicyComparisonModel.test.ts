import { describe, expect, it } from "vitest";

import { buildPolicyComparison } from "@/lib/ppoPolicyComparisonModel";
import type { PPOEvolutionMetric } from "@/lib/ppoEvolutionTypes";

function metric(overrides: Partial<PPOEvolutionMetric> = {}): PPOEvolutionMetric {
  return {
    timestamp: "2026-01-01T00:00:00Z",
    step: 5000,
    mean_reward: 0.5,
    policy_loss: 0.04,
    value_loss: 0.08,
    entropy: 1.0,
    explained_variance: 0.75,
    winrate_rolling_5k: 0.55,
    sharpe_rolling_5k: 1.2,
    action_distribution: { long: 0.4, short: 0.3, hold: 0.3 },
    avg_stop_pct: 0.01,
    avg_target_pct: 0.02,
    ...overrides,
  };
}

describe("buildPolicyComparison", () => {
  it("returns null when fewer than two logs exist", () => {
    expect(buildPolicyComparison([])).toBeNull();
    expect(buildPolicyComparison([metric()])).toBeNull();
  });

  it("compares birth average against current snapshot", () => {
    const result = buildPolicyComparison([
      metric({ mean_reward: 0.4, sharpe_rolling_5k: 1.0 }),
      metric({ mean_reward: 0.42, sharpe_rolling_5k: 1.05 }),
      metric({ mean_reward: 0.44, sharpe_rolling_5k: 1.1 }),
      metric({ mean_reward: 0.46, sharpe_rolling_5k: 1.15 }),
      metric({ mean_reward: 0.48, sharpe_rolling_5k: 1.2 }),
      metric({ mean_reward: 0.8, sharpe_rolling_5k: 1.6 }),
    ]);

    expect(result?.birth.label).toBe("Birth Policy");
    expect(result?.current.label).toBe("Current Policy");
    expect(result?.current.meanReward).toBe(0.8);
    expect(result?.birth.meanReward).toBeCloseTo(0.44);
    expect(result?.deltas.meanReward).toBeCloseTo(0.36);
    expect(result?.deltas.sharpe).toBeCloseTo(0.5);
  });
});
