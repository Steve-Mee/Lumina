import { describe, expect, it } from "vitest";

import {
  buildDecisionHeadline,
  buildReasoningSteps,
} from "@/lib/decisionTheaterModel";
import type { LiveTradingSnapshot } from "@/lib/liveTradingTypes";

const sampleTrading: LiveTradingSnapshot = {
  position: {
    live_qty: 2,
    sim_qty: 2,
    side_signal: "BUY",
    entry_price: 5200,
    open_pnl: 45,
    daily_pnl: 150,
  },
  active_signal: {
    signal: "BUY",
    confidence: 0.81,
    confluence: 0.72,
    reason: "Trend continuation after pullback",
    why_no_trade: "",
    stop: 5188,
    target: 5220,
    strategy: "momentum_breakout",
  },
  regime_confidence: 0.78,
  consecutive_losses: 1,
  pending_reconciliations: 0,
  last_trades: [{ ts: "2026-05-19T11:00:00Z", signal: "BUY", entry: 5190, exit: 5200, qty: 2, pnl: 20, confluence: 0.7 }],
  latest_decision: {
    timestamp: "2026-05-19T11:00:00Z",
    agent_id: "policy",
    confidence: 0.81,
    policy_outcome: "approved",
    decision_context_id: "ctx-1",
    output_summary: "Proceed with long bias",
  },
  current_dream: null,
  runtime_state: null,
};

describe("decisionTheaterModel", () => {
  it("builds reasoning steps from live trading snapshot", () => {
    const steps = buildReasoningSteps(sampleTrading, "TRENDING", "NORMAL", "SIM", 0.22);
    expect(steps.length).toBeGreaterThanOrEqual(4);
    expect(steps[1]?.body).toContain("Trend continuation");
    expect(steps[2]?.title).toContain("Confluence");
  });

  it("uses why_no_trade in policy step for HOLD signals", () => {
    const holdTrading: LiveTradingSnapshot = {
      ...sampleTrading,
      position: { ...sampleTrading.position, live_qty: 0 },
      active_signal: {
        ...sampleTrading.active_signal,
        signal: "HOLD",
        why_no_trade: "Confluence below threshold",
      },
      latest_decision: null,
    };
    const steps = buildReasoningSteps(holdTrading, "RANGE", "ELEVATED", "SIM", 0.15);
    const policy = steps.find((step) => step.id === "policy");
    expect(policy?.body).toContain("Confluence below threshold");
  });

  it("headline reflects open position", () => {
    expect(buildDecisionHeadline(sampleTrading, null, "2026-05-19T12:00:00Z")).toContain("LONG");
  });
});
