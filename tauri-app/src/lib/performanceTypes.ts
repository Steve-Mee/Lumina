export type PerformanceSource = "live" | "fallback";

export interface SessionKpis {
  winrate: number;
  sharpeAnnualized: number;
  profitFactor: number;
  maxDrawdownPct: number;
  maxDrawdownUsd: number;
  realizedPnlSession: number;
}

export interface EquityPoint {
  t: number;
  equity: number;
}

export interface DailyPnlPoint {
  t: number;
  dailyPnl: number;
  ts: string | null;
}

export interface PerformanceSnapshot {
  source: PerformanceSource;
  accountEquity: number | null;
  dailyPnl: number;
  openPnl: number;
  sessionKpis: SessionKpis;
  equitySeries: EquityPoint[];
  dailyHistory: DailyPnlPoint[];
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function asNumber(value: unknown, fallback = 0): number {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim()) {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) return parsed;
  }
  return fallback;
}

function parseSessionKpis(raw: unknown): SessionKpis {
  const record = isRecord(raw) ? raw : {};
  return {
    winrate: asNumber(record.winrate),
    sharpeAnnualized: asNumber(record.sharpe_annualized),
    profitFactor: asNumber(record.profit_factor),
    maxDrawdownPct: asNumber(record.max_drawdown_pct),
    maxDrawdownUsd: asNumber(record.max_drawdown_usd),
    realizedPnlSession: asNumber(record.realized_pnl_session),
  };
}

function parseEquitySeries(raw: unknown): EquityPoint[] {
  if (!Array.isArray(raw)) return [];
  const points: EquityPoint[] = [];
  for (const item of raw) {
    if (!isRecord(item)) continue;
    points.push({
      t: asNumber(item.t, points.length),
      equity: asNumber(item.equity),
    });
  }
  return points;
}

function parseDailyHistory(raw: unknown): DailyPnlPoint[] {
  if (!Array.isArray(raw)) return [];
  const points: DailyPnlPoint[] = [];
  for (const item of raw) {
    if (!isRecord(item)) continue;
    points.push({
      t: asNumber(item.t, points.length),
      dailyPnl: asNumber(item.daily_pnl),
      ts: typeof item.ts === "string" ? item.ts : null,
    });
  }
  return points;
}

export function parsePerformanceSnapshot(raw: unknown): PerformanceSnapshot | null {
  if (!isRecord(raw)) return null;

  const sourceRaw = raw.source;
  const source: PerformanceSource = sourceRaw === "live" ? "live" : "fallback";

  return {
    source,
    accountEquity:
      raw.account_equity === null || raw.account_equity === undefined
        ? null
        : asNumber(raw.account_equity, NaN) || null,
    dailyPnl: asNumber(raw.daily_pnl),
    openPnl: asNumber(raw.open_pnl),
    sessionKpis: parseSessionKpis(raw.session_kpis),
    equitySeries: parseEquitySeries(raw.equity_series),
    dailyHistory: parseDailyHistory(raw.daily_history),
  };
}

export const EMPTY_SESSION_KPIS: SessionKpis = {
  winrate: 0,
  sharpeAnnualized: 0,
  profitFactor: 0,
  maxDrawdownPct: 0,
  maxDrawdownUsd: 0,
  realizedPnlSession: 0,
};
