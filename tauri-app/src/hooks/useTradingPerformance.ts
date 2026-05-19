import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import type { TradeRecord } from "@/lib/liveTradingTypes";
import { fetchRecentTrades } from "@/lib/tradesClient";
import { resolveMonitoringApiKey } from "@/lib/monitoringClient";
import type { EquityPoint } from "@/lib/performanceTypes";
import {
  appendEquityPoint,
  buildTradingPerformanceView,
  type TradingPerformanceView,
} from "@/lib/tradingPerformanceModel";
import {
  selectConnectionStatus,
  selectLiveMetrics,
  selectPerformanceLive,
  useCoreStore,
} from "@/store/coreStore";

const TRADES_POLL_MS = 5000;

export function useTradingPerformance(): {
  view: TradingPerformanceView;
  connected: boolean;
  tradesError: Error | null;
  refreshTrades: () => Promise<void>;
} {
  const performance = useCoreStore(selectPerformanceLive);
  const liveMetrics = useCoreStore(selectLiveMetrics);
  const connectionStatus = useCoreStore(selectConnectionStatus);
  const [equityBuffer, setEquityBuffer] = useState<EquityPoint[]>([]);
  const [restTrades, setRestTrades] = useState<TradeRecord[]>([]);
  const [tradesError, setTradesError] = useState<Error | null>(null);
  const lastBackendLen = useRef(0);

  useEffect(() => {
    const backendLen = performance?.equitySeries.length ?? 0;
    if (backendLen > 0 && backendLen !== lastBackendLen.current) {
      lastBackendLen.current = backendLen;
      setEquityBuffer([]);
    }
  }, [performance?.equitySeries.length]);

  useEffect(() => {
    setEquityBuffer((prev) => appendEquityPoint(prev, liveMetrics.equity));
  }, [liveMetrics.equity, liveMetrics.lastUpdatedTs]);

  const refreshTrades = useCallback(async () => {
    if (!resolveMonitoringApiKey()) return;
    try {
      const rows = await fetchRecentTrades(100);
      setRestTrades(rows);
      setTradesError(null);
    } catch (err) {
      setTradesError(err instanceof Error ? err : new Error(String(err)));
    }
  }, []);

  useEffect(() => {
    void refreshTrades();
    const id = window.setInterval(() => void refreshTrades(), TRADES_POLL_MS);
    return () => window.clearInterval(id);
  }, [refreshTrades]);

  const view = useMemo(
    () =>
      buildTradingPerformanceView({
        performance,
        equityBuffer,
        trades: restTrades,
        liveEquity: liveMetrics.equity,
      }),
    [performance, equityBuffer, restTrades, liveMetrics.equity],
  );

  return {
    view,
    connected: connectionStatus === "connected",
    tradesError,
    refreshTrades,
  };
}
