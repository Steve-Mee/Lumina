import { useCallback, useEffect, useMemo, useState } from "react";

import { mergeTradeFeeds } from "@/lib/liveTradingTypes";
import { fetchRecentTrades } from "@/lib/tradesClient";
import { resolveMonitoringApiKey } from "@/lib/monitoringClient";
import { selectConnectionStatus, selectTradingLive, useCoreStore } from "@/store/coreStore";

const TRADES_POLL_MS = 5000;

export function useLiveTrading() {
  const tradingLive = useCoreStore(selectTradingLive);
  const connectionStatus = useCoreStore(selectConnectionStatus);
  const [restTrades, setRestTrades] = useState<ReturnType<typeof mergeTradeFeeds>>([]);
  const [error, setError] = useState<Error | null>(null);

  const refreshTrades = useCallback(async () => {
    if (!resolveMonitoringApiKey()) return;
    try {
      const rows = await fetchRecentTrades(20);
      setRestTrades(rows);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)));
    }
  }, []);

  useEffect(() => {
    void refreshTrades();
    const id = window.setInterval(() => void refreshTrades(), TRADES_POLL_MS);
    return () => window.clearInterval(id);
  }, [refreshTrades]);

  const trades = useMemo(
    () => mergeTradeFeeds(tradingLive?.last_trades ?? [], restTrades).slice(0, 20),
    [tradingLive?.last_trades, restTrades],
  );

  return {
    trading: tradingLive,
    trades,
    connected: connectionStatus === "connected",
    error,
    refresh: refreshTrades,
  };
}
