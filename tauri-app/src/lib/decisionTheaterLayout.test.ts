import { describe, expect, it } from "vitest";

import {
  formatKellyLabel,
  formatPositionSide,
  hasDebugPayload,
  riskHudGlow,
} from "@/lib/decisionTheaterLayout";
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

describe("decisionTheaterLayout", () => {
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
