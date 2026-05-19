import { useCallback, useEffect, useRef, useState } from "react";

import {
  DEFAULT_POLLING_INTERVAL_MS,
  LuminaMetricsFetchError,
  type LuminaMetrics,
} from "@/lib/luminaMetricsModel";
import { fetchLuminaMetrics, resolveMonitoringApiKey } from "@/lib/monitoringClient";

export function useLuminaMetrics(enabled = true) {
  const [metrics, setMetrics] = useState<LuminaMetrics | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [loading, setLoading] = useState(true);
  const [isFetching, setIsFetching] = useState(false);
  const [lastUpdatedAt, setLastUpdatedAt] = useState<number | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const refresh = useCallback(async () => {
    if (!resolveMonitoringApiKey()) {
      setError(new Error("Monitoring API key not configured"));
      setLoading(false);
      return;
    }
    abortRef.current?.abort();
    abortRef.current = new AbortController();
    setIsFetching(true);
    try {
      const data = await fetchLuminaMetrics();
      setMetrics(data);
      setError(null);
      setLastUpdatedAt(Date.now());
      setLoading(false);
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)));
      setLoading(false);
    } finally {
      setIsFetching(false);
    }
  }, []);

  useEffect(() => {
    if (!enabled) {
      setLoading(false);
      return;
    }
    void refresh();
    const id = window.setInterval(() => void refresh(), DEFAULT_POLLING_INTERVAL_MS);
    return () => {
      window.clearInterval(id);
      abortRef.current?.abort();
    };
  }, [enabled, refresh]);

  return { metrics, error, loading, isFetching, refresh, lastUpdatedAt };
}

export { LuminaMetricsFetchError };
