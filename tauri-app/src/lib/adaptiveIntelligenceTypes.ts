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

export interface AdaptiveIntelligenceWsBlock {
  status: Partial<AdaptiveIntelligenceStatus>;
  transition_summary: Partial<AdaptiveTransitionSummary>;
  event_timestamp?: string | null;
}

export interface AdaptiveIntelligenceEventRecord {
  topic?: string;
  producer?: string;
  timestamp?: string;
  metadata?: Record<string, unknown>;
  payload?: Partial<AdaptiveIntelligenceStatus>;
}

export type IntelligenceHealth = "healthy" | "degraded" | "error";

const VALID_TIERS = new Set<IntelligenceTier>(["high", "standard", "light"]);
const VALID_MODES = new Set<IntelligenceMode>(["auto", "force_high", "force_standard", "force_light"]);

function asTier(raw: unknown): IntelligenceTier | null {
  const value = typeof raw === "string" ? raw.trim().toLowerCase() : "";
  if (value === "beast") return "high";
  if (value === "sweet") return "standard";
  return VALID_TIERS.has(value as IntelligenceTier) ? (value as IntelligenceTier) : null;
}

function asMode(raw: unknown): IntelligenceMode {
  const value = typeof raw === "string" ? raw.trim().toLowerCase() : "";
  return VALID_MODES.has(value as IntelligenceMode) ? (value as IntelligenceMode) : "auto";
}

export function normalizeAdaptiveIntelligenceStatus(raw: unknown): AdaptiveIntelligenceStatus | null {
  if (!raw || typeof raw !== "object") return null;
  const record = raw as Record<string, unknown>;
  const nested =
    record.payload && typeof record.payload === "object"
      ? (record.payload as Record<string, unknown>)
      : record.status && typeof record.status === "object"
        ? (record.status as Record<string, unknown>)
        : record;
  const tier = asTier(nested.tier);
  if (!tier) return null;
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
  if (!raw || typeof raw !== "object") return null;
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

export interface ResolveIntelligenceHealthInput {
  status: AdaptiveIntelligenceStatus | null;
  loading?: boolean;
  error?: Error | null;
  transition?: AdaptiveTransitionSummary | null;
}

export function resolveIntelligenceHealth({
  status,
  loading = false,
  error = null,
  transition = null,
}: ResolveIntelligenceHealthInput): IntelligenceHealth {
  if (error || (!status && !loading)) return "error";
  if (!status) return loading ? "degraded" : "error";
  if (status.last_probe_error) return "error";
  if (status.degraded_state || transition?.is_transition) return "degraded";
  if (loading) return "degraded";
  return "healthy";
}

export function filterAdaptiveHistoryEvents(
  events: AdaptiveIntelligenceEventRecord[],
  query: string,
): AdaptiveIntelligenceEventRecord[] {
  const needle = query.trim().toLowerCase();
  if (!needle) return events;
  return events.filter((event) => {
    const payload = event.payload ?? {};
    const haystack = [
      event.timestamp,
      event.topic,
      payload.tier,
      payload.mode,
      payload.recommended_model,
      payload.recommended_provider,
      payload.status_reason,
      payload.reasoning_mode,
    ]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();
    return haystack.includes(needle);
  });
}
