import { describe, expect, it } from "vitest";

import { deriveCitadelWalls, deriveCitadelWallsFromInputs, integrityTier } from "@/lib/riskCitadelMetrics";
import type { CoreStore } from "@/store/coreStore";

function baseState(overrides: Partial<CoreStore> = {}): CoreStore {
  return {
    liveMetrics: {
      equity: 100_000,
      dailyPnlUsd: 150,
      drawdownPct: null,
      winrate: null,
      openPnl: 45,
      regime: "TRENDING",
      regimeConfidence: null,
      consecutiveLosses: null,
      lastUpdatedTs: "2026-05-19T12:00:00Z",
    },
    evolutionState: {
      pendingCount: 0,
      activeMutations: [],
      activeDnaHash: null,
      championFitness: null,
    },
    riskLevel: "NORMAL",
    operatorMode: "SIM",
    reportedMode: "SIM",
    modeSyncStatus: "idle",
    modeSyncError: null,
    connectionStatus: "connected",
    fallbackMode: false,
    safeModeActive: false,
    safeModeSince: null,
    lastSeq: 1,
    lastError: null,
    reconnectAttempt: 0,
    adaptiveIntelligenceStatus: null,
    adaptiveTransitionSummary: null,
    adaptiveLastUpdatedTs: null,
    tradingLive: null,
    fortress: null,
    setConnectionStatus: () => {},
    setFallbackMode: () => {},
    setSafeModeActive: () => {},
    setReconnectAttempt: () => {},
    resetReconnectAttempt: () => {},
    setLastError: () => {},
    hydrateOperatorMode: () => {},
    setOperatorMode: () => {},
    applyTelemetryFrame: () => {},
    resetCoreState: () => {},
    ...overrides,
  };
}

describe("deriveCitadelWalls", () => {
  it("uses live drawdown for drawdown wall when telemetry present", () => {
    const walls = deriveCitadelWalls(
      baseState({
        liveMetrics: {
          ...baseState().liveMetrics,
          drawdownPct: 6,
        },
        fortress: {
          drawdown_pct: 6,
          drawdown_kill_pct: 8,
          kill_switch_active: false,
          mc_drawdown_pct: null,
          pending_reconciliations: 0,
        },
      }),
    );

    const drawdown = walls.find((wall) => wall.id === "drawdown");
    expect(drawdown?.isStandby).toBe(false);
    expect(drawdown?.integrity).toBe(25);
    expect(integrityTier(drawdown!.integrity)).toBe("red");
  });

  it("marks drawdown wall standby when drawdown is null", () => {
    const walls = deriveCitadelWalls(baseState());
    const drawdown = walls.find((wall) => wall.id === "drawdown");
    expect(drawdown?.isStandby).toBe(true);
    expect(drawdown?.integrity).toBe(88);
  });

  it("forces risk wall critical when kill switch active", () => {
    const walls = deriveCitadelWalls(
      baseState({
        riskLevel: "NORMAL",
        fortress: {
          drawdown_pct: 1,
          drawdown_kill_pct: 8,
          kill_switch_active: true,
          mc_drawdown_pct: null,
          pending_reconciliations: 0,
        },
      }),
    );

    const risk = walls.find((wall) => wall.id === "risk");
    expect(risk?.integrity).toBe(15);
    expect(integrityTier(risk!.integrity)).toBe("red");
    expect(risk?.rawValues.kill_switch_active).toBe(1);
  });

  it("builds regime wall from live confidence", () => {
    const walls = deriveCitadelWalls(
      baseState({
        liveMetrics: {
          ...baseState().liveMetrics,
          regimeConfidence: 0.91,
        },
      }),
    );

    const regime = walls.find((wall) => wall.id === "regime");
    expect(regime?.isStandby).toBe(false);
    expect(regime?.integrity).toBe(91);
  });

  it("deriveCitadelWallsFromInputs reacts to drawdown input changes", () => {
    const baseInput = {
      liveMetrics: baseState().liveMetrics,
      riskLevel: "NORMAL" as const,
      fortress: null,
    };

    const standby = deriveCitadelWallsFromInputs({
      ...baseInput,
      liveMetrics: { ...baseInput.liveMetrics, drawdownPct: null },
    });
    const active = deriveCitadelWallsFromInputs({
      ...baseInput,
      liveMetrics: { ...baseInput.liveMetrics, drawdownPct: 6 },
      fortress: {
        drawdown_pct: 6,
        drawdown_kill_pct: 8,
        kill_switch_active: false,
        mc_drawdown_pct: null,
        pending_reconciliations: 0,
      },
    });

    expect(standby.find((wall) => wall.id === "drawdown")?.isStandby).toBe(true);
    expect(active.find((wall) => wall.id === "drawdown")?.isStandby).toBe(false);
    expect(deriveCitadelWalls(baseState({
      liveMetrics: { ...baseState().liveMetrics, drawdownPct: 6 },
      fortress: {
        drawdown_pct: 6,
        drawdown_kill_pct: 8,
        kill_switch_active: false,
        mc_drawdown_pct: null,
        pending_reconciliations: 0,
      },
    }))).toEqual(active);
  });
});
