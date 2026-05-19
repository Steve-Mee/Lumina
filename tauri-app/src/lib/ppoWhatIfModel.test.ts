import { describe, expect, it } from "vitest";

import { predictWhatIf } from "@/lib/ppoWhatIfModel";
import type { PPOEvolutionMetric } from "@/lib/ppoEvolutionTypes";

function metric(overrides: Partial<PPOEvolutionMetric> = {}): PPOEvolutionMetric {
  return {
    timestamp: "2026-01-01T00:00:00Z",
    step: 5000,
    mean_reward: 1.0,
    policy_loss: 0.04,
    value_loss: 0.08,
    entropy: 1.0,
    explained_variance: 0.8,
    winrate_rolling_5k: 0.55,
    sharpe_rolling_5k: 1.5,
    action_distribution: { long: 0.4, short: 0.3, hold: 0.3 },
    avg_stop_pct: 0.01,
    avg_target_pct: 0.02,
    ...overrides,
  };
}

describe("predictWhatIf", () => {
  it("returns baseline-aligned prediction at neutral sliders", () => {
    const prediction = predictWhatIf(metric(), { entropyLevel: 50, riskAversion: 50 });
    expect(prediction.expectedReward).toBeCloseTo(1.0);
    expect(prediction.expectedSharpe).toBeCloseTo(1.5);
    expect(prediction.confidence).toBeCloseTo(0.8);
  });

  it("increases reward with higher entropy and decreases with higher risk aversion", () => {
    const baseline = metric();
    const highEntropy = predictWhatIf(baseline, { entropyLevel: 80, riskAversion: 50 });
    const highRisk = predictWhatIf(baseline, { entropyLevel: 50, riskAversion: 80 });

    expect(highEntropy.expectedReward).toBeGreaterThan(baseline.mean_reward);
    expect(highRisk.expectedReward).toBeLessThan(baseline.mean_reward);
  });
});
