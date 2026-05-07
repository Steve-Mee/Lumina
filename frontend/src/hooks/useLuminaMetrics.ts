import { useCallback, useEffect, useRef, useState } from "react";

/** Canonical dashboard fields (normalized from `/api/monitoring/metrics/json`). */
export interface LuminaMetrics {
  trades_completed: number;
  ppo_steps: number;
  approval_twin_reward: number;
  cpu: number;
  gpu: number;
  ram: number;
  velocity: number;
  phase: string;
  historical_days: number;
  synthetic_percent: number;
  /** `null` when ETA is unknown/unavailable */
  eta_minutes: number | null;
}

/** 1.8 seconden — interval voor automatische polling */
export const DEFAULT_POLLING_INTERVAL_MS = 1800;

export const DEFAULT_METRICS_ENDPOINT = "/api/monitoring/metrics/json";

/** Key used when reading `localStorage.getItem(...)`. Caller may set via UI or devtools */
export const DEFAULT_LUMINA_API_KEY_LS_KEY = "lumina_api_key";

export class LuminaMetricsFetchError extends Error {
  readonly status: number;

  constructor(message: string, status: number, options?: { cause?: unknown }) {
    super(message, options);
    this.name = "LuminaMetricsFetchError";
    this.status = status;
  }
}

const EMPTY_METRICS: LuminaMetrics = {
  trades_completed: 0,
  ppo_steps: 0,
  approval_twin_reward: 0,
  cpu: 0,
  gpu: 0,
  ram: 0,
  velocity: 0,
  phase: "",
  historical_days: 0,
  synthetic_percent: 0,
  eta_minutes: null,
};

type PrometheusEntry = {
  value?: unknown;
  labels?: unknown;
};

const SNAPSHOT_EMBEDDED_KEYS = ["_lumina_ui", "lumina_ui", "lumina_dashboard", "dashboard"] as const;

/** Optional Prometheus-ish base metric names attempted when embedded UI fields are missing (best-effort). */
const PROM_FALLBACK_SUMS: Partial<Record<keyof Omit<LuminaMetrics, "phase" | "eta_minutes">, readonly string[]>> =
  {
    trades_completed: ["lumina_trades_completed_total", "lumina_model_decisions_total"],
    ppo_steps: ["lumina_ppo_training_steps_total", "lumina_ppo_steps_total"],
    approval_twin_reward: ["lumina_approval_twin_reward", "lumina_approval_twin_avg_reward"],
    cpu: ["lumina_hardware_cpu_pct", "lumina_cpu_percent"],
    gpu: ["lumina_hardware_gpu_pct", "lumina_gpu_percent"],
    ram: ["lumina_hardware_ram_pct", "lumina_ram_percent"],
    velocity: ["lumina_training_velocity_trades_per_s", "lumina_training_throughput_ticks_per_s"],
    historical_days: ["lumina_training_historical_days", "lumina_dataset_historical_days"],
    synthetic_percent: ["lumina_training_synthetic_ratio_pct"],
  };

const ETA_CANDIDATES = ["lumina_training_eta_minutes", "lumina_eta_minutes_remaining"];

function resolveApiKey(lsKey: string): string | null {
  try {
    return localStorage.getItem(lsKey)?.trim() || null;
  } catch {
    return null;
  }
}

function toFiniteNumber(raw: unknown, fallback = Number.NaN): number {
  if (typeof raw === "number") {
    return Number.isFinite(raw) ? raw : fallback;
  }
  if (typeof raw === "string" && raw.trim() !== "") {
    const parsed = Number(raw);
    return Number.isFinite(parsed) ? parsed : fallback;
  }
  return fallback;
}

function entryValue(raw: unknown): number | null {
  if (!raw || typeof raw !== "object") {
    return null;
  }
  const v = toFiniteNumber((raw as PrometheusEntry).value);
  return Number.isFinite(v) ? v : null;
}

/** Sum Prometheus collector entries keyed as `metric` or `metric{labels...}`. */
function sumMatchedKeys(snapshot: Record<string, unknown>, base: string): number | null {
  let sum = 0;
  let hit = false;
  for (const [key, payload] of Object.entries(snapshot)) {
    if (key === "_meta") {
      continue;
    }
    if (key !== base && !key.startsWith(`${base}{`)) {
      continue;
    }
    const n = entryValue(payload);
    if (n !== null) {
      sum += n;
      hit = true;
    }
  }
  return hit ? sum : null;
}

function extractPhaseFromSnapshot(snapshot: Record<string, unknown>): string {
  for (const [key, payload] of Object.entries(snapshot)) {
    if (
      !(key.startsWith("lumina_regime_current") || key === "lumina_regime_current") ||
      typeof payload !== "object" ||
      !payload ||
      typeof (payload as PrometheusEntry).labels !== "object" ||
      !(payload as PrometheusEntry).labels
    ) {
      continue;
    }
    const labels = (payload as PrometheusEntry).labels as Record<string, unknown>;
    const regime = labels.regime ?? labels.phase;
    if (regime != null && String(regime).trim() !== "") {
      return String(regime);
    }
  }
  return "";
}

function firstMetricWithAnyKey(snapshot: Record<string, unknown>, bases: readonly string[]): number | null {
  for (const base of bases) {
    const s = sumMatchedKeys(snapshot, base);
    if (s !== null) {
      return s;
    }
  }
  return null;
}

/** Pull partial metrics from arbitrary nested object (camelCase/snake_case tolerant). */
function partialFromLooseUi(obj: unknown): Partial<LuminaMetrics> | null {
  if (!obj || typeof obj !== "object") {
    return null;
  }
  const r = obj as Record<string, unknown>;
  const out: Partial<LuminaMetrics> = {};

  const pickNum = (...names: readonly string[]): number | undefined => {
    for (const name of names) {
      if (!(name in r)) {
        continue;
      }
      const n = toFiniteNumber(r[name]);
      if (Number.isFinite(n)) {
        return n;
      }
    }
    return undefined;
  };

  const pickStr = (...names: readonly string[]): string | undefined => {
    for (const name of names) {
      const v = r[name];
      if (typeof v === "string") {
        return v;
      }
    }
    return undefined;
  };

  const trades = pickNum("trades_completed");
  const ppo = pickNum("ppo_steps");
  const atr = pickNum("approval_twin_reward");
  const cpu = pickNum("cpu");
  const gpu = pickNum("gpu");
  const ram = pickNum("ram");
  const vel = pickNum("velocity");
  const hd = pickNum("historical_days");
  const syn = pickNum("synthetic_percent");
  const eta = pickNum("eta_minutes");
  const ph = pickStr("phase");

  if (Object.prototype.hasOwnProperty.call(r, "eta_minutes") && r.eta_minutes === null) {
    out.eta_minutes = null;
  }

  if (trades !== undefined) {
    out.trades_completed = trades;
  }
  if (ppo !== undefined) {
    out.ppo_steps = ppo;
  }
  if (atr !== undefined) {
    out.approval_twin_reward = atr;
  }
  if (cpu !== undefined) {
    out.cpu = cpu;
  }
  if (gpu !== undefined) {
    out.gpu = gpu;
  }
  if (ram !== undefined) {
    out.ram = ram;
  }
  if (vel !== undefined) {
    out.velocity = vel;
  }
  if (hd !== undefined) {
    out.historical_days = hd;
  }
  if (syn !== undefined) {
    out.synthetic_percent = syn;
  }
  if (!(Object.prototype.hasOwnProperty.call(out, "eta_minutes") && out.eta_minutes === null)) {
    if (eta !== undefined) {
      out.eta_minutes = eta;
    }
  }
  if (ph !== undefined) {
    out.phase = ph;
  }

  return Object.keys(out).length > 0 ? out : null;
}

function shallowUiFromRoot(snapshot: Record<string, unknown>): Partial<LuminaMetrics> | null {
  const direct = partialFromLooseUi(snapshot);
  if (direct) {
    return direct;
  }

  for (const key of SNAPSHOT_EMBEDDED_KEYS) {
    if (Object.prototype.hasOwnProperty.call(snapshot, key)) {
      const u = partialFromLooseUi(snapshot[key]);
      if (u) {
        return u;
      }
    }
  }
  return null;
}

/**
 * Normalize the metrics JSON blob into `{@link LuminaMetrics}`.
 * Supports (a) Prometheus snapshot layout, (b) optional `_lumina_ui`-style payloads.
 */
export function normalizeLuminaMetricsPayload(raw: unknown): LuminaMetrics {
  if (!raw || typeof raw !== "object") {
    return { ...EMPTY_METRICS };
  }

  const snap = raw as Record<string, unknown>;

  const ui = shallowUiFromRoot(snap);
  const uiKeys = new Set(
    ui ? (Object.keys(ui) as (keyof LuminaMetrics)[]) : ([] as (keyof LuminaMetrics)[]),
  );

  const merged: LuminaMetrics = {
    ...EMPTY_METRICS,
    ...(ui ?? {}),
  };

  const phaseUnset = !(uiKeys.has("phase"));
  const phaseEmptyAfterUi = merged.phase.trim() === "";
  if ((phaseUnset || phaseEmptyAfterUi) && phaseEmptyAfterUi) {
    merged.phase = extractPhaseFromSnapshot(snap);
  }

  (Object.keys(PROM_FALLBACK_SUMS) as (keyof typeof PROM_FALLBACK_SUMS)[]).forEach((fieldKey) => {
    if (uiKeys.has(fieldKey as keyof LuminaMetrics)) {
      return;
    }
    const candidates = PROM_FALLBACK_SUMS[fieldKey];
    if (!candidates) {
      return;
    }
    const v = firstMetricWithAnyKey(snap, candidates);
    if (v !== null) {
      merged[fieldKey] = v as LuminaMetrics[typeof fieldKey];
    }
  });

  if (!(uiKeys.has("eta_minutes"))) {
    const etaGuess = firstMetricWithAnyKey(snap, ETA_CANDIDATES);
    if (merged.eta_minutes === null && etaGuess !== null && Number.isFinite(etaGuess)) {
      merged.eta_minutes = etaGuess;
    }
  }

  return merged;
}

export interface UseLuminaMetricsOptions {
  pollingIntervalMs?: number;
  endpoint?: string;
  apiKeyLocalStorageKey?: string;
  enabled?: boolean;
}

export interface UseLuminaMetricsResult {
  metrics: LuminaMetrics | null;
  error: LuminaMetricsFetchError | Error | null;
  /** First load: no usable snapshot committed yet while a fetch is underway */
  loading: boolean;
  /** Whether any request is in flight */
  isFetching: boolean;
  refresh: () => Promise<void>;
  lastUpdatedAt: number | null;
  lastPollingIntervalMs: number;
}

async function fetchMetricsJson(
  endpoint: string,
  apiKey: string | null,
  signal: AbortSignal,
): Promise<LuminaMetrics> {
  const headers: HeadersInit = {
    Accept: "application/json",
  };
  headers["X-API-Key"] = apiKey ?? "";

  const resp = await fetch(endpoint, {
    signal,
    method: "GET",
    credentials: "same-origin",
    headers,
    cache: "no-store",
  });

  if (!resp.ok) {
    const bodyFull = await resp.text().catch(() => "");
    const body = bodyFull.length > 280 ? `${bodyFull.slice(0, 277)}…` : bodyFull;
    const detail =
      body.length > 0
        ? `Monitoring metrics HTTP ${resp.status}: ${body}`
        : `Monitoring metrics HTTP ${resp.status}`;
    throw new LuminaMetricsFetchError(detail.trim(), resp.status);
  }

  let json: unknown;
  try {
    json = await resp.json();
  } catch {
    throw new LuminaMetricsFetchError("Malformed JSON metrics response", resp.status);
  }

  return normalizeLuminaMetricsPayload(json);
}

/** Poll + normalize Lumina monitoring metrics with sane loading/error ergonomics */
export function useLuminaMetrics(options: UseLuminaMetricsOptions = {}): UseLuminaMetricsResult {
  const pollingIntervalMs = options.pollingIntervalMs ?? DEFAULT_POLLING_INTERVAL_MS;
  const endpoint = options.endpoint ?? DEFAULT_METRICS_ENDPOINT;
  const apiKeyLocalStorageKey = options.apiKeyLocalStorageKey ?? DEFAULT_LUMINA_API_KEY_LS_KEY;
  const enabled = options.enabled ?? true;

  const [metrics, setMetrics] = useState<LuminaMetrics | null>(null);
  const [error, setError] = useState<LuminaMetricsFetchError | Error | null>(null);
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
      if (signal.aborted) {
        return;
      }

      const data = await fetchMetricsJson(endpoint, apiKey, signal);

      if (signal.aborted) {
        return;
      }
      setMetrics(data);
      setError(null);
      setLastUpdatedAt(Date.now());
      setLoading(false);
    } catch (e) {
      if (signal.aborted || (e instanceof DOMException && e.name === "AbortError")) {
        return;
      }
      const normalized =
        e instanceof Error ? e : new Error(String(e ?? "Monitoring metrics unknown error"));

      setError(normalized);
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
      setIsFetching(false);
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
    metrics,
    error,
    loading,
    isFetching,
    refresh,
    lastUpdatedAt,
    lastPollingIntervalMs: pollingIntervalMs,
  };
}
