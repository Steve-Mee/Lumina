import { useCallback, useEffect, useState } from "react";

import { normalizeAdaptiveIntelligenceStatus } from "@/lib/adaptiveIntelligenceTypes";
import { fetchAdaptiveIntelligenceLatest } from "@/lib/monitoringClient";
import {
  selectAdaptiveIntelligenceStatus,
  selectAdaptiveLastUpdatedTs,
  selectAdaptiveTransitionSummary,
  selectConnectionStatus,
  useCoreStore,
} from "@/store/coreStore";
import { useBirthStore } from "@/store/birthStore";

const FALLBACK_POLL_MS = 5000;

export function useAdaptiveIntelligenceLive() {
  const wsStatus = useCoreStore(selectAdaptiveIntelligenceStatus);
  const wsTransition = useCoreStore(selectAdaptiveTransitionSummary);
  const wsUpdatedTs = useCoreStore(selectAdaptiveLastUpdatedTs);
  const connectionStatus = useCoreStore(selectConnectionStatus);
  const birthStatus = useBirthStore((state) => state.status?.adaptive_intelligence);

  const [fallbackStatus, setFallbackStatus] = useState(wsStatus);
  const [fallbackTransition, setFallbackTransition] = useState(wsTransition);
  const [error, setError] = useState<Error | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const data = await fetchAdaptiveIntelligenceLatest();
      setFallbackStatus(data.status);
      setFallbackTransition(data.transitionSummary);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)));
    } finally {
      setLoading(false);
    }
  }, []);

  const needsFallback =
    connectionStatus !== "connected" || wsStatus === null;

  useEffect(() => {
    if (!needsFallback) {
      setLoading(false);
      return;
    }
    void refresh();
    const id = window.setInterval(() => void refresh(), FALLBACK_POLL_MS);
    return () => window.clearInterval(id);
  }, [needsFallback, refresh]);

  const birthFallback = birthStatus
    ? normalizeAdaptiveIntelligenceStatus(birthStatus)
    : null;

  const status = wsStatus ?? fallbackStatus ?? birthFallback;
  const transitionSummary = wsTransition ?? fallbackTransition;
  const lastUpdatedAt = wsUpdatedTs
    ? Date.parse(wsUpdatedTs)
    : status
      ? Date.now()
      : null;

  return {
    status,
    transitionSummary,
    error,
    loading: loading && !status,
    connected: connectionStatus === "connected" && wsStatus !== null,
    refresh,
    lastUpdatedAt: Number.isFinite(lastUpdatedAt ?? NaN) ? lastUpdatedAt : null,
  };
}
