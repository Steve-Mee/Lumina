import { describe, expect, it } from "vitest";

import {
  clamp01,
  gaugePercent,
  normalizeEntropy,
  normalizeExplainedVariance,
  normalizeMeanReward,
  normalizeWinrate,
} from "@/lib/ppoEvolutionMetrics";
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

describe("ppoEvolutionMetrics", () => {
  it("clamps values to 0–1", () => {
    expect(clamp01(-0.2)).toBe(0);
    expect(clamp01(1.5)).toBe(1);
    expect(clamp01(0.4)).toBe(0.4);
  });

  it("normalizes mean reward symmetrically against log history", () => {
    const logs = [metric({ mean_reward: -1 }), metric({ mean_reward: 1 })];
    expect(normalizeMeanReward(-1, logs)).toBe(0);
    expect(normalizeMeanReward(1, logs)).toBe(1);
    expect(normalizeMeanReward(0, logs)).toBe(0.5);
  });

  it("normalizes entropy, explained variance, and winrate", () => {
    expect(normalizeEntropy(1)).toBe(0.5);
    expect(normalizeExplainedVariance(0.75)).toBe(0.75);
    expect(normalizeWinrate(0.6)).toBe(0.6);
    expect(gaugePercent(0.667)).toBe(67);
  });
});
