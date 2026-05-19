export interface TradeRecord {
  ts: string | null;
  signal: string;
  entry: number;
  exit: number;
  qty: number;
  pnl: number;
  confluence: number;
  symbol?: string | null;
  slippage_points?: number | null;
  fill_latency_ms?: number | null;
}

export interface ActiveSignal {
  signal: string;
  confidence: number;
  confluence: number;
  reason: string;
  why_no_trade: string;
  stop: number;
  target: number;
  strategy: string;
}

export interface PositionSnapshot {
  live_qty: number;
  sim_qty: number;
  side_signal: string;
  entry_price: number;
  open_pnl: number;
  daily_pnl: number;
}

export interface LatestDecision {
  timestamp: string | null;
  agent_id: string | null;
  confidence: number;
  policy_outcome: string;
  decision_context_id: string;
  output_summary: string;
}

export interface LiveTradingSnapshot {
  position: PositionSnapshot;
  active_signal: ActiveSignal;
  regime_confidence: number;
  consecutive_losses: number;
  pending_reconciliations: number;
  last_trades: TradeRecord[];
  latest_decision: LatestDecision | null;
  current_dream: Record<string, unknown> | null;
  runtime_state: Record<string, unknown> | null;
}

export interface AdaptiveIntelligenceWsBlock {
  status?: unknown;
  transition_summary?: unknown;
  event_timestamp?: string | null;
}

function asNumber(value: unknown, fallback = 0): number {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim()) {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) return parsed;
  }
  return fallback;
}

function asInt(value: unknown, fallback = 0): number {
  return Math.trunc(asNumber(value, fallback));
}

function parseTradeRecord(raw: unknown): TradeRecord | null {
  if (!raw || typeof raw !== "object") return null;
  const row = raw as Record<string, unknown>;
  return {
    ts: typeof row.ts === "string" ? row.ts : null,
    signal: String(row.signal ?? ""),
    entry: asNumber(row.entry),
    exit: asNumber(row.exit),
    qty: asInt(row.qty),
    pnl: asNumber(row.pnl),
    confluence: asNumber(row.confluence),
    symbol: typeof row.symbol === "string" ? row.symbol : null,
    slippage_points: row.slippage_points == null ? null : asNumber(row.slippage_points),
    fill_latency_ms: row.fill_latency_ms == null ? null : asNumber(row.fill_latency_ms),
  };
}

export function parseLiveTradingSnapshot(raw: unknown): LiveTradingSnapshot | null {
  if (!raw || typeof raw !== "object") return null;
  const block = raw as Record<string, unknown>;
  const positionRaw = block.position;
  const signalRaw = block.active_signal;
  if (!positionRaw || typeof positionRaw !== "object") return null;
  if (!signalRaw || typeof signalRaw !== "object") return null;
  const position = positionRaw as Record<string, unknown>;
  const signal = signalRaw as Record<string, unknown>;

  const tradesRaw = block.last_trades;
  const lastTrades = Array.isArray(tradesRaw)
    ? tradesRaw.map(parseTradeRecord).filter((row): row is TradeRecord => row !== null)
    : [];

  let latestDecision: LatestDecision | null = null;
  const decisionRaw = block.latest_decision;
  if (decisionRaw && typeof decisionRaw === "object") {
    const d = decisionRaw as Record<string, unknown>;
    latestDecision = {
      timestamp: typeof d.timestamp === "string" ? d.timestamp : null,
      agent_id: typeof d.agent_id === "string" ? d.agent_id : null,
      confidence: asNumber(d.confidence),
      policy_outcome: String(d.policy_outcome ?? ""),
      decision_context_id: String(d.decision_context_id ?? ""),
      output_summary: String(d.output_summary ?? ""),
    };
  }

  return {
    position: {
      live_qty: asInt(position.live_qty),
      sim_qty: asInt(position.sim_qty),
      side_signal: String(position.side_signal ?? ""),
      entry_price: asNumber(position.entry_price),
      open_pnl: asNumber(position.open_pnl),
      daily_pnl: asNumber(position.daily_pnl),
    },
    active_signal: {
      signal: String(signal.signal ?? "HOLD"),
      confidence: asNumber(signal.confidence),
      confluence: asNumber(signal.confluence),
      reason: String(signal.reason ?? ""),
      why_no_trade: String(signal.why_no_trade ?? ""),
      stop: asNumber(signal.stop),
      target: asNumber(signal.target),
      strategy: String(signal.strategy ?? ""),
    },
    regime_confidence: asNumber(block.regime_confidence),
    consecutive_losses: asInt(block.consecutive_losses),
    pending_reconciliations: asInt(block.pending_reconciliations),
    last_trades: lastTrades,
    latest_decision: latestDecision,
    current_dream:
      block.current_dream && typeof block.current_dream === "object"
        ? (block.current_dream as Record<string, unknown>)
        : null,
    runtime_state:
      block.runtime_state && typeof block.runtime_state === "object"
        ? (block.runtime_state as Record<string, unknown>)
        : null,
  };
}

export function deriveWinrateFromTrades(trades: TradeRecord[]): number | null {
  const closed = trades.filter((trade) => trade.qty !== 0 || trade.pnl !== 0);
  if (closed.length === 0) return null;
  const wins = closed.filter((trade) => trade.pnl > 0).length;
  return wins / closed.length;
}

export function mergeTradeFeeds(
  wsTrades: TradeRecord[],
  restTrades: TradeRecord[],
): TradeRecord[] {
  const merged = new Map<string, TradeRecord>();
  for (const trade of [...wsTrades, ...restTrades]) {
    const key = trade.ts ? `${trade.ts}:${trade.signal}:${trade.qty}` : JSON.stringify(trade);
    merged.set(key, { ...merged.get(key), ...trade });
  }
  return [...merged.values()].sort((a, b) => {
    const ta = a.ts ? Date.parse(a.ts) : 0;
    const tb = b.ts ? Date.parse(b.ts) : 0;
    return tb - ta;
  });
}
