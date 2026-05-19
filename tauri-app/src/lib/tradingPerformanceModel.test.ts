import { describe, expect, it } from "vitest";

import { parsePerformanceSnapshot } from "@/lib/performanceTypes";
import {
  appendEquityPoint,
  buildCumulativePnlFromTrades,
  buildTradingPerformanceView,
  formatProfitFactor,
  formatWinrate,
  mergeBackendEquitySeries,
} from "@/lib/tradingPerformanceModel";

describe("parsePerformanceSnapshot", () => {
  it("parses a live performance block", () => {
    const parsed = parsePerformanceSnapshot({
      source: "live",
      account_equity: 101_000,
      daily_pnl: 250,
      open_pnl: 50,
      session_kpis: {
        winrate: 0.7,
        sharpe_annualized: 1.5,
        profit_factor: 2.0,
        max_drawdown_pct: -1.2,
        max_drawdown_usd: 300,
        realized_pnl_session: 1000,
      },
      equity_series: [{ t: 0, equity: 100_000 }],
      daily_history: [{ t: 0, daily_pnl: 100, ts: "2026-05-19T00:00:00Z" }],
    });

    expect(parsed?.source).toBe("live");
    expect(parsed?.sessionKpis.sharpeAnnualized).toBe(1.5);
    expect(parsed?.equitySeries).toHaveLength(1);
  });
});

describe("tradingPerformanceModel", () => {
  it("formats winrate and profit factor", () => {
    expect(formatWinrate(0.724)).toBe("72.4%");
    expect(formatProfitFactor(0)).toBe("—");
    expect(formatProfitFactor(1.45)).toBe("1.45");
  });

  it("appends unique equity points", () => {
    const first = appendEquityPoint([], 100_000);
    expect(first).toHaveLength(1);
    const second = appendEquityPoint(first, 100_000);
    expect(second).toHaveLength(1);
    const third = appendEquityPoint(second, 100_500);
    expect(third).toHaveLength(2);
  });

  it("merges backend series with live buffer using reindexed tail", () => {
    const merged = mergeBackendEquitySeries(
      [
        { t: 0, equity: 100_000 },
        { t: 1, equity: 100_500 },
      ],
      [
        { t: 0, equity: 100_500 },
        { t: 1, equity: 100_750 },
      ],
    );
    expect(merged).toHaveLength(3);
    expect(merged[2].equity).toBe(100_750);
    expect(merged[2].t).toBe(2);
  });

  it("builds cumulative pnl from trades", () => {
    const chart = buildCumulativePnlFromTrades([
      { ts: "2026-05-19T12:00:00Z", signal: "BUY", entry: 1, exit: 2, qty: 1, pnl: 100, confluence: 0 },
      { ts: "2026-05-19T11:00:00Z", signal: "SELL", entry: 1, exit: 2, qty: 1, pnl: -50, confluence: 0 },
    ]);
    expect(chart).toHaveLength(2);
    expect(chart[1].cumulativePnl).toBe(50);
  });

  it("builds a trading performance view", () => {
    const view = buildTradingPerformanceView({
      performance: parsePerformanceSnapshot({
        source: "live",
        account_equity: 100_000,
        daily_pnl: 100,
        open_pnl: 25,
        session_kpis: {
          winrate: 0.6,
          sharpe_annualized: 1.1,
          profit_factor: 1.3,
          max_drawdown_pct: -2,
          max_drawdown_usd: 200,
          realized_pnl_session: 500,
        },
        equity_series: [{ t: 0, equity: 99_000 }, { t: 1, equity: 100_000 }],
        daily_history: [],
      }),
      equityBuffer: [{ t: 0, equity: 100_000 }, { t: 1, equity: 100_100 }],
      trades: [],
      liveEquity: 100_100,
    });

    expect(view.hasLiveData).toBe(true);
    expect(view.dailyPnl).toBe(100);
    expect(view.equityChart.length).toBeGreaterThanOrEqual(2);
  });
});
