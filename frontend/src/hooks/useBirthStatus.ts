import { useCallback, useEffect, useRef, useState } from "react";
import { DEFAULT_LUMINA_API_KEY_LS_KEY } from "./useLuminaMetrics";

export const BIRTH_STATUS_ENDPOINT = "/api/birth/status";
export const BIRTH_START_ENDPOINT = "/api/birth/start";
export const DEFAULT_BIRTH_POLL_MS = 2000;

export interface BirthProgress {
  trades_done: number;
  target_trades: number;
  progress_pct: number;
  ppo_steps: number;
  stage: string;
}

export interface BirthStatus {
  status: string;
  message?: string;
  progress?: BirthProgress;
  progress_pct?: number;
  elapsed_seconds?: number;
  error?: string;
  result?: unknown;
  artifacts_ok?: boolean;
  artifacts_label?: string;
  phase_label?: string;
  target_trades?: number;
}

export class BirthStatusFetchError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "BirthStatusFetchError";
    this.status = status;
  }
}

function resolveApiKey(lsKey: string): string | null {
  try {
    return localStorage.getItem(lsKey)?.trim() || null;
  } catch {
    return null;
  }
}

async function fetchBirthStatus(
  endpoint: string,
  apiKey: string | null,
  signal: AbortSignal,
): Promise<BirthStatus> {
  const headers: HeadersInit = { Accept: "application/json" };
  if (apiKey) {
    headers["X-API-Key"] = apiKey;
  }

  const resp = await fetch(endpoint, {
    signal,
    method: "GET",
    credentials: "same-origin",
    headers,
    cache: "no-store",
  });

  if (!resp.ok) {
    const body = await resp.text().catch(() => "");
    throw new BirthStatusFetchError(
      body.length > 0 ? `Birth status HTTP ${resp.status}: ${body}` : `Birth status HTTP ${resp.status}`,
      resp.status,
    );
  }

  return (await resp.json()) as BirthStatus;
}

export async function startBirthPhase(
  targetTrades: number,
  options?: { force?: boolean; apiKeyLocalStorageKey?: string },
): Promise<BirthStatus> {
  const apiKey = resolveApiKey(options?.apiKeyLocalStorageKey ?? DEFAULT_LUMINA_API_KEY_LS_KEY);
  const params = new URLSearchParams({
    target_trades: String(targetTrades),
    force: String(Boolean(options?.force)),
  });
  const headers: HeadersInit = { Accept: "application/json" };
  if (apiKey) {
    headers["X-API-Key"] = apiKey;
  }

  const resp = await fetch(`${BIRTH_START_ENDPOINT}?${params}`, {
    method: "POST",
    credentials: "same-origin",
    headers,
    cache: "no-store",
  });

  if (!resp.ok) {
    const body = await resp.text().catch(() => "");
    throw new BirthStatusFetchError(
      body.length > 0 ? `Birth start HTTP ${resp.status}: ${body}` : `Birth start HTTP ${resp.status}`,
      resp.status,
    );
  }

  return (await resp.json()) as BirthStatus;
}

export interface UseBirthStatusOptions {
  pollingIntervalMs?: number;
  endpoint?: string;
  apiKeyLocalStorageKey?: string;
  enabled?: boolean;
}

export interface UseBirthStatusResult {
  status: BirthStatus | null;
  error: BirthStatusFetchError | Error | null;
  loading: boolean;
  isFetching: boolean;
  refresh: () => Promise<void>;
  lastUpdatedAt: number | null;
  startBirth: (targetTrades: number, force?: boolean) => Promise<void>;
  starting: boolean;
}

export function useBirthStatus(options: UseBirthStatusOptions = {}): UseBirthStatusResult {
  const pollingIntervalMs = options.pollingIntervalMs ?? DEFAULT_BIRTH_POLL_MS;
  const endpoint = options.endpoint ?? BIRTH_STATUS_ENDPOINT;
  const apiKeyLocalStorageKey = options.apiKeyLocalStorageKey ?? DEFAULT_LUMINA_API_KEY_LS_KEY;
  const enabled = options.enabled ?? true;

  const [status, setStatus] = useState<BirthStatus | null>(null);
  const [error, setError] = useState<BirthStatusFetchError | Error | null>(null);
  const [loading, setLoading] = useState(true);
  const [isFetching, setIsFetching] = useState(false);
  const [starting, setStarting] = useState(false);
  const [lastUpdatedAt, setLastUpdatedAt] = useState<number | null>(null);

  const abortRef = useRef<AbortController | null>(null);
  const fetchGenerationRef = useRef(0);

  const refresh = useCallback(async () => {
    const generation = ++fetchGenerationRef.current;
    abortRef.current?.abort();
    abortRef.current = new AbortController();
    const signal = abortRef.current.signal;

    setIsFetching(true);
    try {
      const apiKey = resolveApiKey(apiKeyLocalStorageKey);
      const data = await fetchBirthStatus(endpoint, apiKey, signal);
      if (signal.aborted) {
        return;
      }
      setStatus(data);
      setError(null);
      setLastUpdatedAt(Date.now());
      setLoading(false);
    } catch (e) {
      if (signal.aborted || (e instanceof DOMException && e.name === "AbortError")) {
        return;
      }
      setError(e instanceof Error ? e : new Error(String(e)));
      setLoading(false);
    } finally {
      if (generation === fetchGenerationRef.current) {
        setIsFetching(false);
      }
    }
  }, [apiKeyLocalStorageKey, endpoint]);

  const startBirth = useCallback(
    async (targetTrades: number, force = false) => {
      setStarting(true);
      setError(null);
      try {
        const result = await startBirthPhase(targetTrades, {
          force,
          apiKeyLocalStorageKey,
        });
        setStatus((prev) => ({ ...prev, ...result }));
        await refresh();
      } catch (e) {
        setError(e instanceof Error ? e : new Error(String(e)));
      } finally {
        setStarting(false);
      }
    },
    [apiKeyLocalStorageKey, refresh],
  );

  useEffect(() => {
    if (!enabled) {
      setLoading(false);
      return;
    }
    void refresh();
    const id = window.setInterval(() => void refresh(), pollingIntervalMs);
    return () => {
      window.clearInterval(id);
      abortRef.current?.abort();
    };
  }, [enabled, pollingIntervalMs, refresh]);

  return {
    status,
    error,
    loading,
    isFetching,
    refresh,
    lastUpdatedAt,
    startBirth,
    starting,
  };
}
