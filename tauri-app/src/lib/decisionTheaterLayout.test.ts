import { describe, expect, it } from "vitest";

import {
  DECISION_STAGE_HERO_MAX,
  formatKellyLabel,
  formatPositionSide,
  hasDebugPayload,
  resolveDecisionTradePreview,
  resolveDecisionStageHero,
  riskHudGlow,
} from "@/lib/decisionTheaterLayout";
import type { DecisionBrief } from "@/lib/decisionTheaterModel";
import type { LiveTradingSnapshot } from "@/lib/liveTradingTypes";

const baseTrading: LiveTradingSnapshot = {
  position: {
    live_qty: 0,
    sim_qty: 0,
    side_signal: "HOLD",
    entry_price: 0,
    open_pnl: 0,
    daily_pnl: 0,
  },
  active_signal: {
    signal: "HOLD",
    confidence: 0.5,
    confluence: 0.5,
    reason: "",
    why_no_trade: "",
    stop: 0,
    target: 0,
    strategy: "",
  },
  regime_confidence: 0.5,
  consecutive_losses: 0,
  pending_reconciliations: 0,
  last_trades: [],
  latest_decision: null,
  current_dream: null,
  runtime_state: null,
};

const baseBrief: DecisionBrief = {
  headline: "Hold",
  verdict: "hold",
  steps: [],
  metrics: {
    overallConfidence: 0.62,
    riskScore: 74,
    kellyFraction: 0.18,
    regime: "Trend",
  },
  proposalHash: null,
  lastUpdatedTs: null,
};

describe("decisionTheaterLayout", () => {
  it("resolveDecisionStageHero caps visible hero signals at two", () => {
    expect(DECISION_STAGE_HERO_MAX).toBe(2);

    const sim = resolveDecisionStageHero("SIM", baseBrief, baseTrading, "NORMAL", false);
    const visible = [sim.primary, sim.secondary].filter(Boolean);
    expect(visible.length).toBeLessThanOrEqual(2);
    expect(sim.primary.label).toBe("Confidence");
    expect(sim.secondary).toBeNull();
    expect(sim.overflow.length).toBeGreaterThan(0);
  });

  it("REAL calm mode hides Kelly secondary unless risk is HIGH+", () => {
    const calmHold = resolveDecisionStageHero(
      "REAL",
      { ...baseBrief, verdict: "enter", proposalHash: "abc" },
      baseTrading,
      "NORMAL",
      false,
    );
    expect(calmHold.primary.label).toBe("Risk");
    expect(calmHold.secondary).toBeNull();

    const highRisk = resolveDecisionStageHero(
      "REAL",
      { ...baseBrief, verdict: "enter", proposalHash: "abc" },
      baseTrading,
      "HIGH",
      false,
    );
    expect(highRisk.secondary?.label).toBe("Kelly");
  });

  it("resolveDecisionTradePreview caps rows", () => {
    const trades = [
      { signal: "BUY", pnl: 1, entry: 1, exit: 2, qty: 1, ts: "1" },
      { signal: "SELL", pnl: 2, entry: 1, exit: 2, qty: 1, ts: "2" },
      { signal: "BUY", pnl: 3, entry: 1, exit: 2, qty: 1, ts: "3" },
    ];
    const { preview, overflowCount } = resolveDecisionTradePreview(trades);
    expect(preview.length).toBe(2);
    expect(overflowCount).toBe(1);
  });

  it("formatKellyLabel reflects REAL quarter-kelly cap", () => {
    expect(formatKellyLabel("REAL", 0.22)).toBe("22% · Quarter-Kelly");
    expect(formatKellyLabel("SIM", 0.22)).toBe("22% · SIM cap");
  });

  it("riskHudGlow maps risk levels to glow tokens", () => {
    expect(riskHudGlow("NORMAL")).toBe("emerald");
    expect(riskHudGlow("HIGH")).toBe("amber");
    expect(riskHudGlow("CRITICAL")).toBe("amber");
  });

  it("hasDebugPayload detects dream or runtime state", () => {
    expect(hasDebugPayload(null)).toBe(false);
    expect(hasDebugPayload(baseTrading)).toBe(false);
    expect(
      hasDebugPayload({ ...baseTrading, current_dream: { phase: "test" } }),
    ).toBe(true);
    expect(
      hasDebugPayload({ ...baseTrading, runtime_state: { alive: true } }),
    ).toBe(true);
  });

  it("formatPositionSide derives side from qty", () => {
    expect(formatPositionSide(baseTrading)).toBe("HOLD");
    expect(
      formatPositionSide({
        ...baseTrading,
        position: { ...baseTrading.position, live_qty: 2 },
      }),
    ).toBe("LONG");
    expect(
      formatPositionSide({
        ...baseTrading,
        position: { ...baseTrading.position, live_qty: -1 },
      }),
    ).toBe("SHORT");
  });
});
