import type { TradeRecord } from "@/lib/liveTradingTypes";
import type { EquityPoint, PerformanceSnapshot, SessionKpis } from "@/lib/performanceTypes";

export const MAX_EQUITY_BUFFER = 240;

export interface TradingPerformanceView {
  equityChart: EquityPoint[];
  dailyPnlChart: Array<{ t: number; dailyPnl: number; label: string }>;
  cumulativePnlChart: Array<{ t: number; cumulativePnl: number; label: string }>;
  kpis: SessionKpis;
  dailyPnl: number;
  openPnl: number;
  sessionRealizedPnl: number;
  accountEquity: number | null;
  source: PerformanceSnapshot["source"] | "buffer";
  hasLiveData: boolean;
}

export function formatWinrate(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

export function formatSharpe(value: number): string {
  return value.toFixed(2);
}

export function formatMaxDrawdownPct(value: number): string {
  const magnitude = Math.abs(value);
  return `${magnitude.toFixed(1)}%`;
}

export function formatProfitFactor(value: number): string {
  if (value <= 0) return "—";
  return value.toFixed(2);
}

export function formatUsd(value: number | null, opts?: { signed?: boolean }): string {
  if (value === null || !Number.isFinite(value)) return "—";
  const signed = opts?.signed ?? true;
  const prefix = signed && value >= 0 ? "+" : "";
  return `${prefix}$${value.toLocaleString(undefined, {
    maximumFractionDigits: 0,
    minimumFractionDigits: 0,
  })}`;
}

export function pnlToneClass(value: number | null): string {
  if (value === null || value === 0) return "text-muted-foreground";
  return value > 0 ? "text-emerald-300" : "text-red-300";
}

export function kpiToneClass(
  kind: "sharpe" | "drawdown",
  value: number,
  drawdownKillPct = 8,
): string {
  if (kind === "sharpe") {
    if (value >= 1.0) return "text-emerald-300";
    if (value >= 0.5) return "text-cyan-200/90";
    return "text-amber-200/90";
  }
  const magnitude = Math.abs(value);
  if (magnitude >= drawdownKillPct * 0.5) return "text-amber-200/90";
  return "text-cyan-200/90";
}

export function appendEquityPoint(
  series: EquityPoint[],
  equity: number | null,
  maxPoints = MAX_EQUITY_BUFFER,
): EquityPoint[] {
  if (equity === null || !Number.isFinite(equity)) return series;
  const last = series[series.length - 1];
  if (last && last.equity === equity) return series;
  const nextT = last ? last.t + 1 : 0;
  const next = [...series, { t: nextT, equity }];
  if (next.length <= maxPoints) return next;
  return next.slice(next.length - maxPoints);
}

export function mergeBackendEquitySeries(
  backendSeries: EquityPoint[],
  buffer: EquityPoint[],
): EquityPoint[] {
  if (backendSeries.length === 0) return buffer;
  if (buffer.length === 0) return backendSeries;

  const backendLast = backendSeries[backendSeries.length - 1];
  let bufferTail = buffer;
  if (buffer[0]?.equity === backendLast.equity) {
    bufferTail = buffer.slice(1);
  }
  if (bufferTail.length === 0) return backendSeries;

  const offset = backendLast.t + 1;
  const reindexed = bufferTail.map((point, idx) => ({
    t: offset + idx,
    equity: point.equity,
  }));
  return [...backendSeries, ...reindexed].slice(-MAX_EQUITY_BUFFER);
}

export function buildCumulativePnlFromTrades(trades: TradeRecord[]): Array<{
  t: number;
  cumulativePnl: number;
  label: string;
}> {
  const chronological = [...trades].reverse();
  let cumulative = 0;
  return chronological.map((trade, index) => {
    cumulative += trade.pnl;
    const label =
      trade.ts != null
        ? new Date(trade.ts).toLocaleTimeString(undefined, {
            hour: "2-digit",
            minute: "2-digit",
          })
        : `#${index + 1}`;
    return { t: index, cumulativePnl: cumulative, label };
  });
}

export function buildEquityFallbackFromTrades(
  trades: TradeRecord[],
  baselineEquity: number | null,
): EquityPoint[] {
  if (baselineEquity === null || trades.length === 0) return [];
  const chronological = [...trades].reverse();
  let cumulative = 0;
  return chronological.map((trade, index) => {
    cumulative += trade.pnl;
    return { t: index, equity: baselineEquity - cumulative + trade.pnl };
  });
}

export function buildTradingPerformanceView(input: {
  performance: PerformanceSnapshot | null;
  equityBuffer: EquityPoint[];
  trades: TradeRecord[];
  liveEquity: number | null;
}): TradingPerformanceView {
  const performance = input.performance;
  const kpis = performance?.sessionKpis ?? {
    winrate: 0,
    sharpeAnnualized: 0,
    profitFactor: 0,
    maxDrawdownPct: 0,
    maxDrawdownUsd: 0,
    realizedPnlSession: 0,
  };

  const backendSeries = performance?.equitySeries ?? [];
  let equityChart = mergeBackendEquitySeries(backendSeries, input.equityBuffer);
  if (equityChart.length === 0 && input.liveEquity !== null) {
    equityChart = [{ t: 0, equity: input.liveEquity }];
  }

  const cumulativePnlChart = buildCumulativePnlFromTrades(input.trades);
  const dailyPnlChart =
    performance?.dailyHistory.map((point, index) => ({
      t: point.t,
      dailyPnl: point.dailyPnl,
      label: point.ts
        ? new Date(point.ts).toLocaleDateString(undefined, { month: "short", day: "numeric" })
        : `D${index + 1}`,
    })) ?? [];

  const hasLiveData =
    (performance?.source === "live" && backendSeries.length > 0) ||
    input.equityBuffer.length > 1 ||
    input.liveEquity !== null;

  return {
    equityChart,
    dailyPnlChart,
    cumulativePnlChart,
    kpis,
    dailyPnl: performance?.dailyPnl ?? 0,
    openPnl: performance?.openPnl ?? 0,
    sessionRealizedPnl: kpis.realizedPnlSession,
    accountEquity: performance?.accountEquity ?? input.liveEquity,
    source: performance?.source ?? "buffer",
    hasLiveData,
  };
}
