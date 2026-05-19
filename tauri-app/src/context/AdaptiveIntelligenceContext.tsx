import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

import { useAdaptiveIntelligenceLive } from "@/hooks/useAdaptiveIntelligenceLive";
import { useLuminaMetrics } from "@/hooks/useLuminaMetrics";
import type { AdaptiveIntelligenceEventRecord } from "@/lib/adaptiveIntelligenceTypes";
import {
  fetchAdaptiveIntelligenceHistory,
  fetchMonitoringHealth,
  type MonitoringHealthSnapshot,
} from "@/lib/monitoringClient";
import type { LuminaMetrics } from "@/lib/luminaMetricsModel";
import { selectApiKeyConfigured, useApiKeyStore } from "@/store/apiKeyStore";

const HISTORY_POLL_MS = 10_000;
const HEALTH_POLL_MS = 5000;

interface AdaptiveIntelligenceContextValue {
  status: ReturnType<typeof useAdaptiveIntelligenceLive>["status"];
  transitionSummary: ReturnType<typeof useAdaptiveIntelligenceLive>["transitionSummary"];
  history: AdaptiveIntelligenceEventRecord[];
  metrics: LuminaMetrics | null;
  healthSnapshot: MonitoringHealthSnapshot | null;
  connected: boolean;
  loading: boolean;
  error: Error | null;
  apiKeyConfigured: boolean;
  refresh: () => Promise<void>;
  lastUpdatedAt: number | null;
}

const AdaptiveIntelligenceContext = createContext<AdaptiveIntelligenceContextValue | null>(null);

export function AdaptiveIntelligenceProvider({ children }: { children: ReactNode }) {
  const live = useAdaptiveIntelligenceLive();
  const apiKeyConfigured = useApiKeyStore(selectApiKeyConfigured);
  const metricsState = useLuminaMetrics(apiKeyConfigured);
  const [history, setHistory] = useState<AdaptiveIntelligenceEventRecord[]>([]);
  const [healthSnapshot, setHealthSnapshot] = useState<MonitoringHealthSnapshot | null>(null);
  const [historyError, setHistoryError] = useState<Error | null>(null);
  const prevTransitionRef = useRef(false);

  const refreshHistory = useCallback(async () => {
    if (!apiKeyConfigured) return;
    try {
      const rows = await fetchAdaptiveIntelligenceHistory(200);
      setHistory(rows);
      setHistoryError(null);
    } catch (err) {
      setHistoryError(err instanceof Error ? err : new Error(String(err)));
    }
  }, [apiKeyConfigured]);

  const refreshHealth = useCallback(async () => {
    try {
      const health = await fetchMonitoringHealth();
      setHealthSnapshot(health);
    } catch {
      // health endpoint is unauthenticated; ignore transient errors
    }
  }, []);

  const refresh = useCallback(async () => {
    await Promise.all([
      live.refresh(),
      metricsState.refresh(),
      refreshHistory(),
      refreshHealth(),
    ]);
  }, [live, metricsState, refreshHistory, refreshHealth]);

  useEffect(() => {
    if (!apiKeyConfigured) return;
    void refreshHistory();
    const id = window.setInterval(() => void refreshHistory(), HISTORY_POLL_MS);
    return () => window.clearInterval(id);
  }, [refreshHistory, apiKeyConfigured]);

  useEffect(() => {
    void refreshHealth();
    const id = window.setInterval(() => void refreshHealth(), HEALTH_POLL_MS);
    return () => window.clearInterval(id);
  }, [refreshHealth]);

  useEffect(() => {
    const isTransition = Boolean(live.transitionSummary?.is_transition);
    if (isTransition && !prevTransitionRef.current) {
      void refreshHistory();
    }
    prevTransitionRef.current = isTransition;
  }, [live.transitionSummary, refreshHistory]);

  const value = useMemo<AdaptiveIntelligenceContextValue>(
    () => ({
      status: live.status,
      transitionSummary: live.transitionSummary,
      history,
      metrics: metricsState.metrics,
      healthSnapshot,
      connected: live.connected,
      loading: live.loading || metricsState.loading,
      error: live.error ?? metricsState.error ?? historyError,
      apiKeyConfigured,
      refresh,
      lastUpdatedAt: live.lastUpdatedAt ?? metricsState.lastUpdatedAt,
    }),
    [
      live.status,
      live.transitionSummary,
      live.connected,
      live.loading,
      live.error,
      live.lastUpdatedAt,
      history,
      metricsState.metrics,
      metricsState.loading,
      metricsState.error,
      metricsState.lastUpdatedAt,
      healthSnapshot,
      historyError,
      refresh,
      apiKeyConfigured,
    ],
  );

  useEffect(() => {
    useApiKeyStore.getState().hydrate();
  }, []);

  useEffect(() => {
    if (apiKeyConfigured) {
      void refresh();
    }
  }, [apiKeyConfigured, refresh]);

  return (
    <AdaptiveIntelligenceContext.Provider value={value}>
      {children}
    </AdaptiveIntelligenceContext.Provider>
  );
}

export function useAdaptiveIntelligenceContext(): AdaptiveIntelligenceContextValue {
  const ctx = useContext(AdaptiveIntelligenceContext);
  if (!ctx) {
    throw new Error("useAdaptiveIntelligenceContext must be used within AdaptiveIntelligenceProvider");
  }
  return ctx;
}
