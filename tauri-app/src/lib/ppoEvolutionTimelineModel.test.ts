import { describe, expect, it } from "vitest";

import {
  buildEvolutionTimeline,
  DEFAULT_TIMELINE_MAX_STEPS,
} from "@/lib/ppoEvolutionTimelineModel";
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

describe("buildEvolutionTimeline", () => {
  it("returns empty array for no logs", () => {
    expect(buildEvolutionTimeline([])).toEqual([]);
  });

  it("limits entries to maxSteps", () => {
    const logs = Array.from({ length: 60 }, (_, index) =>
      metric({ step: (index + 1) * 5000 }),
    );
    expect(buildEvolutionTimeline(logs).length).toBe(DEFAULT_TIMELINE_MAX_STEPS);
    expect(buildEvolutionTimeline(logs)[0]?.step).toBe(55_000);
  });

  it("detects reward spike, entropy dip, winrate surge, and value fit drop", () => {
    const logs = [
      metric({
        step: 5000,
        mean_reward: 0.4,
        entropy: 1.0,
        winrate_rolling_5k: 0.5,
        explained_variance: 0.8,
      }),
      metric({
        step: 10_000,
        mean_reward: 0.55,
        entropy: 0.85,
        winrate_rolling_5k: 0.58,
        explained_variance: 0.6,
      }),
    ];

    const timeline = buildEvolutionTimeline(logs);
    expect(timeline[0]?.events).toEqual([]);
    expect(timeline[1]?.events.map((event) => event.type)).toEqual([
      "reward_spike",
      "entropy_dip",
      "winrate_surge",
      "explained_variance_drop",
    ]);
  });

  it("does not flag first entry with delta events", () => {
    const timeline = buildEvolutionTimeline([metric({ step: 5000 })]);
    expect(timeline).toHaveLength(1);
    expect(timeline[0]?.events).toEqual([]);
  });
});
