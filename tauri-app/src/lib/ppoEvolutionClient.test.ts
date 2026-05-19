import { describe, expect, it } from "vitest";

import { parsePpoEvolutionLine, resolvePpoEvolutionWsUrl } from "@/lib/ppoEvolutionClient";

describe("ppoEvolutionClient", () => {
  it("falls back to localhost ws url when env unset", () => {
    expect(resolvePpoEvolutionWsUrl()).toBe("ws://localhost:8000/ws/ppo-evolution");
  });

  it("resolves ws url from http base override", () => {
    expect(resolvePpoEvolutionWsUrl("http://127.0.0.1:8000")).toBe(
      "ws://127.0.0.1:8000/ws/ppo-evolution",
    );
  });

  it("parses valid jsonl metric line", () => {
    const line = JSON.stringify({
      timestamp: "2026-05-19T12:00:00+00:00",
      step: 5000,
      mean_reward: 1.25,
      policy_loss: 0.04,
      value_loss: 0.11,
      entropy: 0.33,
      explained_variance: 0.72,
      winrate_rolling_5k: 0.58,
      sharpe_rolling_5k: 1.2,
      action_distribution: { long: 0.6, short: 0.3, hold: 0.1 },
      avg_stop_pct: 0.009,
      avg_target_pct: 0.018,
    });
    const metric = parsePpoEvolutionLine(line);
    expect(metric).not.toBeNull();
    expect(metric?.step).toBe(5000);
    expect(metric?.action_distribution.long).toBe(0.6);
  });

  it("returns null for invalid lines", () => {
    expect(parsePpoEvolutionLine("")).toBeNull();
    expect(parsePpoEvolutionLine("pong")).toBeNull();
    expect(parsePpoEvolutionLine("{not-json")).toBeNull();
    expect(parsePpoEvolutionLine('{"step": "bad"}')).toBeNull();
  });
});
