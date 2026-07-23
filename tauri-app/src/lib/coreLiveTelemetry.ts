import { parseFortressSnapshot, type FortressSnapshot } from "@/lib/fortressTypes";
import { parseLiveTradingSnapshot, type LiveTradingSnapshot } from "@/lib/liveTradingTypes";
import { parsePerformanceSnapshot, type PerformanceSnapshot } from "@/lib/performanceTypes";
import { parseRealOpsSnapshot, type RealOpsSnapshot } from "@/lib/realOpsTypes";

export interface ActiveMutation {
  hash: string;
  timestamp: string | null;
  challenger_count: number;
}

export interface AdaptiveIntelligenceWsBlock {
  status?: unknown;
  transition_summary?: unknown;
  event_timestamp?: string | null;
}

export type { FortressSnapshot } from "@/lib/fortressTypes";
export type { PerformanceSnapshot } from "@/lib/performanceTypes";
export type { RealOpsSnapshot } from "@/lib/realOpsTypes";

export interface NinjaTraderTelemetry {
  connected: boolean;
  account: string;
  last_bar_ts: string | null;
  state: string;
  /** Fabric safe mode: NORMAL | SAFE | FULL_SAFE | UNKNOWN */
  safe_mode?: string;
  fabric_target?: string;
  gateway?: string;
  session_id?: string;
  last_state_hash?: string;
  recent_alerts?: number;
  metrics?: Record<string, number | string>;
}

export interface CoreLiveTelemetry {
  mode: string;
  equity: number | null;
  regime: string;
  risk_level: string;
  active_mutations: ActiveMutation[];
  source_ts: string | null;
  ninjatrader?: NinjaTraderTelemetry | null;
  adaptive_intelligence?: AdaptiveIntelligenceWsBlock | null;
  live_trading?: LiveTradingSnapshot | null;
  fortress?: FortressSnapshot | null;
  performance?: PerformanceSnapshot | null;
  real_ops?: RealOpsSnapshot | null;
}

export interface TelemetryFrame {
  type: "telemetry";
  seq: number;
  ts: string;
  payload: CoreLiveTelemetry;
}

export function resolveCoreLiveUrl(override?: string): string {
  if (override) {
    return override;
  }
  const envWs = import.meta.env.VITE_LUMINA_BACKEND_WS_URL;
  if (envWs) {
    return envWs;
  }
  const httpBase =
    import.meta.env.VITE_LUMINA_BACKEND_URL ?? "http://127.0.0.1:8000";
  return (
    httpBase.replace(/^http/, "ws").replace(/\/$/, "") + "/ws/core/live"
  );
}

export function resolveCoreLiveHttpUrl(): string {
  const base =
    import.meta.env.VITE_LUMINA_BACKEND_URL ?? "http://127.0.0.1:8000";
  return base.replace(/\/$/, "") + "/api/core/live";
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function parseActiveMutation(value: unknown): ActiveMutation | null {
  if (!isRecord(value)) {
    return null;
  }
  return {
    hash: typeof value.hash === "string" ? value.hash : "",
    timestamp:
      typeof value.timestamp === "string" ? value.timestamp : null,
    challenger_count:
      typeof value.challenger_count === "number"
        ? value.challenger_count
        : 0,
  };
}

function parseNinjaTraderTelemetry(value: unknown): NinjaTraderTelemetry | null {
  if (!isRecord(value)) {
    return null;
  }
  const metricsRaw = value.metrics;
  const metrics =
    metricsRaw && typeof metricsRaw === "object" && metricsRaw !== null
      ? (metricsRaw as Record<string, number | string>)
      : undefined;
  return {
    connected: value.connected === true,
    account: typeof value.account === "string" ? value.account : "",
    last_bar_ts:
      typeof value.last_bar_ts === "string" ? value.last_bar_ts : null,
    state: typeof value.state === "string" ? value.state : "disconnected",
    safe_mode: typeof value.safe_mode === "string" ? value.safe_mode : undefined,
    fabric_target:
      typeof value.fabric_target === "string" ? value.fabric_target : undefined,
    gateway: typeof value.gateway === "string" ? value.gateway : undefined,
    session_id: typeof value.session_id === "string" ? value.session_id : undefined,
    last_state_hash:
      typeof value.last_state_hash === "string" ? value.last_state_hash : undefined,
    recent_alerts:
      typeof value.recent_alerts === "number" ? value.recent_alerts : undefined,
    metrics,
  };
}

export function parseTelemetryPayload(value: unknown): CoreLiveTelemetry | null {
  if (!isRecord(value)) {
    return null;
  }

  const mutationsRaw = value.active_mutations;
  const active_mutations = Array.isArray(mutationsRaw)
    ? mutationsRaw
        .map(parseActiveMutation)
        .filter((item): item is ActiveMutation => item !== null)
    : [];

  const adaptiveBlock = value.adaptive_intelligence;
  const liveTrading = parseLiveTradingSnapshot(value.live_trading);
  const fortress = parseFortressSnapshot(value.fortress);
  const performance = parsePerformanceSnapshot(value.performance);
  const realOps = parseRealOpsSnapshot(value.real_ops);
  const ninjatrader = parseNinjaTraderTelemetry(value.ninjatrader);

  return {
    mode: typeof value.mode === "string" ? value.mode : "unknown",
    equity:
      typeof value.equity === "number"
        ? value.equity
        : value.equity === null
          ? null
          : null,
    regime: typeof value.regime === "string" ? value.regime : "UNKNOWN",
    risk_level:
      typeof value.risk_level === "string" ? value.risk_level : "UNKNOWN",
    active_mutations,
    source_ts:
      typeof value.source_ts === "string" ? value.source_ts : null,
    ninjatrader,
    adaptive_intelligence:
      adaptiveBlock && typeof adaptiveBlock === "object"
        ? (adaptiveBlock as AdaptiveIntelligenceWsBlock)
        : null,
    live_trading: liveTrading,
    fortress,
    performance,
    real_ops: realOps,
  };
}

export function parseTelemetryFrame(raw: unknown): TelemetryFrame | null {
  if (!isRecord(raw) || raw.type !== "telemetry") {
    return null;
  }
  if (typeof raw.seq !== "number" || typeof raw.ts !== "string") {
    return null;
  }
  const payload = parseTelemetryPayload(raw.payload);
  if (!payload) {
    return null;
  }
  return {
    type: "telemetry",
    seq: raw.seq,
    ts: raw.ts,
    payload,
  };
}