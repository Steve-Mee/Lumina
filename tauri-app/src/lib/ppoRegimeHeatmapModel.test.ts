import { describe, expect, it } from "vitest";

import { buildRegimeHeatmap } from "@/lib/ppoRegimeHeatmapModel";
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

describe("buildRegimeHeatmap", () => {
  it("returns four regime cells with sample counts", () => {
    const cells = buildRegimeHeatmap([
      metric({ mean_reward: 0.4 }),
      metric({
        mean_reward: 0.8,
        action_distribution: { long: 0.7, short: 0.2, hold: 0.1 },
      }),
      metric({ entropy: 1.5, mean_reward: 0.2, policy_loss: 0.04 }),
    ]);

    expect(cells).toHaveLength(4);
    expect(cells.reduce((sum, cell) => sum + cell.sampleCount, 0)).toBe(3);
    expect(cells.find((cell) => cell.regime === "high_volatility")?.sampleCount).toBe(1);
  });

  it("normalizes intensity across populated regimes", () => {
    const cells = buildRegimeHeatmap([
      metric({ mean_reward: 0.2 }),
      metric({
        mean_reward: 0.9,
        action_distribution: { long: 0.8, short: 0.1, hold: 0.1 },
      }),
    ]);

    const trendingUp = cells.find((cell) => cell.regime === "trending_up");
    expect(trendingUp?.intensity).toBeGreaterThan(0);
  });
});
