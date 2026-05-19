import { create } from "zustand";

import { postOperatorMode } from "@/lib/modeClient";
import {
  normalizeAdaptiveIntelligenceStatus,
  normalizeTransitionSummary,
  type AdaptiveIntelligenceStatus,
  type AdaptiveTransitionSummary,
} from "@/lib/adaptiveIntelligenceTypes";
import type { TelemetryFrame } from "@/lib/websocket";
import {
  deriveWinrateFromTrades,
  type LiveTradingSnapshot,
} from "@/lib/liveTradingTypes";
import type { FortressSnapshot } from "@/lib/fortressTypes";
import type { PerformanceSnapshot } from "@/lib/performanceTypes";
import type { RealOpsSnapshot } from "@/lib/realOpsTypes";

export type TradingMode = "SIM" | "REAL";

export type ConnectionStatus =
  | "disconnected"
  | "connecting"
  | "connected"
  | "reconnecting";

export type RiskLevel =
  | "UNKNOWN"
  | "NORMAL"
  | "ELEVATED"
  | "HIGH"
  | "CRITICAL";

export type ModeSyncStatus = "idle" | "pending" | "error";

export interface LiveMetrics {
  equity: number | null;
  dailyPnlUsd: number | null;
  drawdownPct: number | null;
  winrate: number | null;
  openPnl: number | null;
  regime: string;
  regimeConfidence: number | null;
  consecutiveLosses: number | null;
  lastUpdatedTs: string | null;
}

export interface EvolutionMutation {
  hash: string;
  timestamp: string | null;
  challengerCount: number;
}

export interface EvolutionState {
  pendingCount: number;
  activeMutations: EvolutionMutation[];
  activeDnaHash: string | null;
  championFitness: number | null;
}

const OPERATOR_MODE_STORAGE_KEY = "lumina.operatorMode";

interface CoreStoreState {
  liveMetrics: LiveMetrics;
  evolutionState: EvolutionState;
  riskLevel: RiskLevel;
  operatorMode: TradingMode;
  reportedMode: TradingMode | null;
  modeSyncStatus: ModeSyncStatus;
  modeSyncError: string | null;
  connectionStatus: ConnectionStatus;
  fallbackMode: boolean;
  safeModeActive: boolean;
  safeModeSince: string | null;
  lastSeq: number | null;
  lastError: string | null;
  reconnectAttempt: number;
  adaptiveIntelligenceStatus: AdaptiveIntelligenceStatus | null;
  adaptiveTransitionSummary: AdaptiveTransitionSummary | null;
  adaptiveLastUpdatedTs: string | null;
  tradingLive: LiveTradingSnapshot | null;
  fortress: FortressSnapshot | null;
  performanceLive: PerformanceSnapshot | null;
  realOpsLive: RealOpsSnapshot | null;
}

interface CoreStoreActions {
  setConnectionStatus: (status: ConnectionStatus) => void;
  setFallbackMode: (active: boolean) => void;
  setSafeModeActive: (active: boolean, since?: string | null) => void;
  setReconnectAttempt: (attempt: number) => void;
  resetReconnectAttempt: () => void;
  setLastError: (message: string | null) => void;
  hydrateOperatorMode: () => void;
  setOperatorMode: (mode: TradingMode) => void;
  applyTelemetryFrame: (frame: TelemetryFrame) => void;
  resetCoreState: () => void;
}

export type CoreStore = CoreStoreState & CoreStoreActions;

const INITIAL_LIVE_METRICS: LiveMetrics = {
  equity: null,
  dailyPnlUsd: null,
  drawdownPct: null,
  winrate: null,
  openPnl: null,
  regime: "UNKNOWN",
  regimeConfidence: null,
  consecutiveLosses: null,
  lastUpdatedTs: null,
};

const INITIAL_EVOLUTION_STATE: EvolutionState = {
  pendingCount: 0,
  activeMutations: [],
  activeDnaHash: null,
  championFitness: null,
};

const INITIAL_STATE: CoreStoreState = {
  liveMetrics: INITIAL_LIVE_METRICS,
  evolutionState: INITIAL_EVOLUTION_STATE,
  riskLevel: "UNKNOWN",
  operatorMode: "SIM",
  reportedMode: null,
  modeSyncStatus: "idle",
  modeSyncError: null,
  connectionStatus: "disconnected",
  fallbackMode: false,
  safeModeActive: false,
  safeModeSince: null,
  lastSeq: null,
  lastError: null,
  reconnectAttempt: 0,
  adaptiveIntelligenceStatus: null,
  adaptiveTransitionSummary: null,
  adaptiveLastUpdatedTs: null,
  tradingLive: null,
  fortress: null,
  performanceLive: null,
  realOpsLive: null,
};

const RISK_LEVELS: RiskLevel[] = [
  "UNKNOWN",
  "NORMAL",
  "ELEVATED",
  "HIGH",
  "CRITICAL",
];

function normalizeTradingMode(raw: string): TradingMode {
  return raw.toLowerCase() === "real" ? "REAL" : "SIM";
}

function readStoredOperatorMode(): TradingMode | null {
  if (typeof window === "undefined") {
    return null;
  }
  try {
    const stored = window.localStorage.getItem(OPERATOR_MODE_STORAGE_KEY);
    if (stored === "SIM" || stored === "REAL") {
      return stored;
    }
  } catch {
    return null;
  }
  return null;
}

function persistOperatorMode(mode: TradingMode): void {
  if (typeof window === "undefined") {
    return;
  }
  try {
    window.localStorage.setItem(OPERATOR_MODE_STORAGE_KEY, mode);
  } catch {
    // ignore storage failures
  }
}

function normalizeRiskLevel(raw: string): RiskLevel {
  const upper = raw.toUpperCase();
  if (RISK_LEVELS.includes(upper as RiskLevel)) {
    return upper as RiskLevel;
  }
  return "UNKNOWN";
}

function mapEvolutionMutations(
  mutations: TelemetryFrame["payload"]["active_mutations"],
): EvolutionMutation[] {
  return mutations.map((mutation) => ({
    hash: mutation.hash,
    timestamp: mutation.timestamp,
    challengerCount: mutation.challenger_count,
  }));
}

export const useCoreStore = create<CoreStore>((set, get) => ({
  ...INITIAL_STATE,
  setConnectionStatus: (status) => set({ connectionStatus: status }),
  setFallbackMode: (active) => set({ fallbackMode: active }),
  setSafeModeActive: (active, since = null) =>
    set({
      safeModeActive: active,
      safeModeSince: active ? (since ?? new Date().toISOString()) : null,
    }),
  setReconnectAttempt: (attempt) => set({ reconnectAttempt: attempt }),
  resetReconnectAttempt: () => set({ reconnectAttempt: 0 }),
  setLastError: (message) => set({ lastError: message }),
  hydrateOperatorMode: () => {
    const stored = readStoredOperatorMode();
    if (stored) {
      set({ operatorMode: stored });
    }
  },
  setOperatorMode: (mode) => {
    const current = get().operatorMode;
    if (current === mode) {
      return;
    }

    persistOperatorMode(mode);
    set({
      operatorMode: mode,
      modeSyncStatus: "pending",
      modeSyncError: null,
    });

    void postOperatorMode(mode).then((result) => {
      if (result.ok) {
        set({ modeSyncStatus: "idle", modeSyncError: null });
        return;
      }
      set({
        modeSyncStatus: "error",
        modeSyncError: result.error ?? "Failed to sync mode with backend",
      });
    });
  },
  applyTelemetryFrame: (frame) =>
    set((state) => {
      const { payload } = frame;
      const activeMutations = mapEvolutionMutations(payload.active_mutations);
      const adaptiveBlock = payload.adaptive_intelligence;
      const adaptiveStatus = adaptiveBlock
        ? normalizeAdaptiveIntelligenceStatus(adaptiveBlock.status ?? adaptiveBlock)
        : null;
      const adaptiveTransition = adaptiveBlock
        ? normalizeTransitionSummary(adaptiveBlock.transition_summary)
        : null;
      const adaptiveTs =
        adaptiveBlock?.event_timestamp ??
        adaptiveStatus?.timestamp ??
        payload.source_ts;

      const tradingLive = payload.live_trading ?? null;
      const fortress = payload.fortress ?? null;
      const performanceLive = payload.performance ?? null;
      const realOpsLive = payload.real_ops ?? null;
      const winrate =
        performanceLive?.sessionKpis.winrate ??
        (tradingLive ? deriveWinrateFromTrades(tradingLive.last_trades) : null);

      const drawdownPct =
        fortress?.drawdown_pct ??
        (fortress?.mc_drawdown_pct != null ? fortress.mc_drawdown_pct : null);

      return {
        reportedMode: normalizeTradingMode(payload.mode),
        riskLevel: normalizeRiskLevel(payload.risk_level),
        liveMetrics: {
          ...state.liveMetrics,
          equity: payload.equity,
          regime: payload.regime,
          lastUpdatedTs: payload.source_ts,
          regimeConfidence: tradingLive?.regime_confidence ?? null,
          dailyPnlUsd: tradingLive?.position.daily_pnl ?? null,
          openPnl: tradingLive?.position.open_pnl ?? null,
          consecutiveLosses: tradingLive?.consecutive_losses ?? null,
          drawdownPct,
          winrate,
        },
        evolutionState: {
          ...state.evolutionState,
          pendingCount: activeMutations.length,
          activeMutations,
        },
        adaptiveIntelligenceStatus: adaptiveBlock ? adaptiveStatus : null,
        adaptiveTransitionSummary: adaptiveBlock ? adaptiveTransition : null,
        adaptiveLastUpdatedTs: adaptiveBlock ? adaptiveTs : null,
        tradingLive,
        fortress,
        performanceLive,
        realOpsLive,
        lastSeq: frame.seq,
        lastError: null,
      };
    }),
  resetCoreState: () => set({ ...INITIAL_STATE }),
}));

export const selectLiveMetrics = (state: CoreStore) => state.liveMetrics;
export const selectEvolutionState = (state: CoreStore) => state.evolutionState;
export const selectRiskLevel = (state: CoreStore) => state.riskLevel;
export const selectCurrentMode = (state: CoreStore) => state.operatorMode;
export const selectOperatorMode = (state: CoreStore) => state.operatorMode;
export const selectReportedMode = (state: CoreStore) => state.reportedMode;
export const selectModeSyncStatus = (state: CoreStore) => state.modeSyncStatus;
export const selectConnectionStatus = (state: CoreStore) => state.connectionStatus;
export const selectFallbackMode = (state: CoreStore) => state.fallbackMode;
export const selectSafeModeActive = (state: CoreStore) => state.safeModeActive;
export const selectSafeModeSince = (state: CoreStore) => state.safeModeSince;
export const selectAdaptiveIntelligenceStatus = (state: CoreStore) =>
  state.adaptiveIntelligenceStatus;
export const selectAdaptiveTransitionSummary = (state: CoreStore) =>
  state.adaptiveTransitionSummary;
export const selectAdaptiveLastUpdatedTs = (state: CoreStore) => state.adaptiveLastUpdatedTs;
export const selectTradingLive = (state: CoreStore) => state.tradingLive;
export const selectFortress = (state: CoreStore) => state.fortress;
export const selectPerformanceLive = (state: CoreStore) => state.performanceLive;
export const selectRealOpsLive = (state: CoreStore) => state.realOpsLive;
