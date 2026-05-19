import { describe, expect, it } from "vitest";

import { evaluatePolicyHealth } from "@/lib/ppoPolicyHealth";
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

describe("evaluatePolicyHealth", () => {
  it("marks all metrics healthy at typical SB3 values", () => {
    const snapshot = evaluatePolicyHealth(metric());
    expect(snapshot.policyLoss.status).toBe("healthy");
    expect(snapshot.valueLoss.status).toBe("healthy");
    expect(snapshot.explainedVariance.status).toBe("healthy");
  });

  it("escalates policy and value loss into watch and critical bands", () => {
    const watch = evaluatePolicyHealth(
      metric({ policy_loss: 0.1, value_loss: 0.2, explained_variance: 0.55 }),
    );
    expect(watch.policyLoss.status).toBe("watch");
    expect(watch.valueLoss.status).toBe("watch");
    expect(watch.explainedVariance.status).toBe("watch");

    const critical = evaluatePolicyHealth(
      metric({ policy_loss: 0.2, value_loss: 0.35, explained_variance: 0.2 }),
    );
    expect(critical.policyLoss.status).toBe("critical");
    expect(critical.valueLoss.status).toBe("critical");
    expect(critical.explainedVariance.status).toBe("critical");
  });
});
