import { useCallback, useEffect, useRef, useState } from "react";
import { DEFAULT_LUMINA_API_KEY_LS_KEY } from "./useLuminaMetrics";

export const ADAPTIVE_INTELLIGENCE_LATEST_ENDPOINT = "/api/monitoring/adaptive-intelligence/latest";

export const DEFAULT_ADAPTIVE_INTELLIGENCE_POLL_MS = 2000;

export type IntelligenceTier = "high" | "standard" | "light";
export type IntelligenceMode = "auto" | "force_high" | "force_standard" | "force_light";

export interface AdaptiveIntelligenceStatus {
  tier: IntelligenceTier;
  mode: IntelligenceMode;
  reasoning_mode: string;
  degraded_state: boolean;
  status_reason: string;
  recommended_model: string;
  recommended_provider: string;
  context_length: number;
  last_probe_error: string | null;
  source?: string | null;
  timestamp?: string | null;
}

export interface AdaptiveTransitionSummary {
  is_transition: boolean;
  changed_fields: string[];
  from_state: Partial<AdaptiveIntelligenceStatus> | null;
  to_state: Partial<AdaptiveIntelligenceStatus> | null;
}

export interface AdaptiveIntelligenceLatestResponse {
  topic?: string;
  producer?: string;
  timestamp?: string;
  metadata?: Record<string, unknown>;
  payload?: Partial<AdaptiveIntelligenceStatus>;
  transition_summary?: Partial<AdaptiveTransitionSummary>;
}

export class AdaptiveIntelligenceFetchError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "AdaptiveIntelligenceFetchError";
    this.status = status;
  }
}

const VALID_TIERS = new Set<IntelligenceTier>(["high", "standard", "light"]);
const VALID_MODES = new Set<IntelligenceMode>(["auto", "force_high", "force_standard", "force_light"]);

function resolveApiKey(lsKey: string): string | null {
  try {
    return localStorage.getItem(lsKey)?.trim() || null;
  } catch {
    return null;
  }
}

function asTier(raw: unknown): IntelligenceTier | null {
  const value = typeof raw === "string" ? raw.trim().toLowerCase() : "";
  if (value === "beast") {
    return "high";
  }
  if (value === "sweet") {
    return "standard";
  }
  return VALID_TIERS.has(value as IntelligenceTier) ? (value as IntelligenceTier) : null;
}

function asMode(raw: unknown): IntelligenceMode {
  const value = typeof raw === "string" ? raw.trim().toLowerCase() : "";
  return VALID_MODES.has(value as IntelligenceMode) ? (value as IntelligenceMode) : "auto";
}

/** Normalize birth-service dict or monitoring envelope payload into canonical status. */
export function normalizeAdaptiveIntelligenceStatus(raw: unknown): AdaptiveIntelligenceStatus | null {
  if (!raw || typeof raw !== "object") {
    return null;
  }
  const record = raw as Record<string, unknown>;
  const nested =
    record.payload && typeof record.payload === "object"
      ? (record.payload as Record<string, unknown>)
      : record;
  const tier = asTier(nested.tier);
  if (!tier) {
    return null;
  }
  return {
    tier,
    mode: asMode(nested.mode),
    reasoning_mode: String(nested.reasoning_mode ?? "unknown"),
    degraded_state: Boolean(nested.degraded_state),
    status_reason: String(nested.status_reason ?? "").trim(),
    recommended_model: String(nested.recommended_model ?? "unknown"),
    recommended_provider: String(nested.recommended_provider ?? "ollama"),
    context_length: Math.max(0, Number(nested.context_length) || 0),
    last_probe_error:
      nested.last_probe_error == null || nested.last_probe_error === ""
        ? null
        : String(nested.last_probe_error),
    source: nested.source == null ? null : String(nested.source),
    timestamp: nested.timestamp == null ? null : String(nested.timestamp),
  };
}

export function normalizeTransitionSummary(raw: unknown): AdaptiveTransitionSummary | null {
  if (!raw || typeof raw !== "object") {
    return null;
  }
  const record = raw as Record<string, unknown>;
  const changed = Array.isArray(record.changed_fields)
    ? record.changed_fields.filter((item): item is string => typeof item === "string")
    : [];
  return {
    is_transition: Boolean(record.is_transition),
    changed_fields: changed,
    from_state:
      record.from_state && typeof record.from_state === "object"
        ? normalizeAdaptiveIntelligenceStatus(record.from_state)
        : null,
    to_state:
      record.to_state && typeof record.to_state === "object"
        ? normalizeAdaptiveIntelligenceStatus(record.to_state)
        : null,
  };
}

async function fetchAdaptiveIntelligenceLatest(
  endpoint: string,
  apiKey: string | null,
  signal: AbortSignal,
): Promise<{ status: AdaptiveIntelligenceStatus | null; transitionSummary: AdaptiveTransitionSummary | null }> {
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

  if (resp.status === 404 || resp.status === 204) {
    return { status: null, transitionSummary: null };
  }

  if (!resp.ok) {
    const body = await resp.text().catch(() => "");
    throw new AdaptiveIntelligenceFetchError(
      body.length > 0 ? `Adaptive intelligence HTTP ${resp.status}: ${body}` : `Adaptive intelligence HTTP ${resp.status}`,
      resp.status,
    );
  }

  const json = (await resp.json()) as AdaptiveIntelligenceLatestResponse;
  if (!json || typeof json !== "object" || Object.keys(json).length === 0) {
    return { status: null, transitionSummary: null };
  }

  return {
    status: normalizeAdaptiveIntelligenceStatus(json),
    transitionSummary: normalizeTransitionSummary(json.transition_summary),
  };
}

export interface UseAdaptiveIntelligenceOptions {
  pollingIntervalMs?: number;
  endpoint?: string;
  apiKeyLocalStorageKey?: string;
  enabled?: boolean;
}

export interface UseAdaptiveIntelligenceResult {
  status: AdaptiveIntelligenceStatus | null;
  transitionSummary: AdaptiveTransitionSummary | null;
  error: AdaptiveIntelligenceFetchError | Error | null;
  loading: boolean;
  isFetching: boolean;
  refresh: () => Promise<void>;
  lastUpdatedAt: number | null;
}

export function useAdaptiveIntelligence(options: UseAdaptiveIntelligenceOptions = {}): UseAdaptiveIntelligenceResult {
  const pollingIntervalMs = options.pollingIntervalMs ?? DEFAULT_ADAPTIVE_INTELLIGENCE_POLL_MS;
  const endpoint = options.endpoint ?? ADAPTIVE_INTELLIGENCE_LATEST_ENDPOINT;
  const apiKeyLocalStorageKey = options.apiKeyLocalStorageKey ?? DEFAULT_LUMINA_API_KEY_LS_KEY;
  const enabled = options.enabled ?? true;

  const [status, setStatus] = useState<AdaptiveIntelligenceStatus | null>(null);
  const [transitionSummary, setTransitionSummary] = useState<AdaptiveTransitionSummary | null>(null);
  const [error, setError] = useState<AdaptiveIntelligenceFetchError | Error | null>(null);
  const [loading, setLoading] = useState(true);
  const [isFetching, setIsFetching] = useState(false);
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
      const data = await fetchAdaptiveIntelligenceLatest(endpoint, apiKey, signal);
      if (signal.aborted) {
        return;
      }
      setStatus(data.status);
      setTransitionSummary(data.transitionSummary);
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
    transitionSummary,
    error,
    loading,
    isFetching,
    refresh,
    lastUpdatedAt,
  };
}
