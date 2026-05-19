import type {
  AdaptiveIntelligenceStatus,
  AdaptiveTransitionSummary,
  IntelligenceTier,
} from "../hooks/useAdaptiveIntelligence";

export type IntelligenceHealth = "healthy" | "degraded" | "error";

export const TIER_VISUAL: Record<
  IntelligenceTier,
  { label: string; color: string; border: string; glow: string }
> = {
  high: {
    label: "HIGH",
    color: "#fbbf24",
    border: "rgba(251,191,36,0.45)",
    glow: "rgba(251,191,36,0.22)",
  },
  standard: {
    label: "STD",
    color: "#00ff9f",
    border: "rgba(0,255,159,0.4)",
    glow: "rgba(0,255,159,0.2)",
  },
  light: {
    label: "LIGHT",
    color: "#94a3b8",
    border: "rgba(148,163,184,0.35)",
    glow: "rgba(148,163,184,0.15)",
  },
};

export const HEALTH_DOT: Record<IntelligenceHealth, { color: string; glow: string; label: string }> = {
  healthy: { color: "#00ff9f", glow: "rgba(0,255,159,0.55)", label: "Healthy" },
  degraded: { color: "#fbbf24", glow: "rgba(251,191,36,0.55)", label: "Degraded" },
  error: { color: "#ef4444", glow: "rgba(239,68,68,0.55)", label: "Error" },
};

export function formatTierLabel(tier: IntelligenceTier): string {
  return TIER_VISUAL[tier]?.label ?? tier.toUpperCase();
}

export function formatProviderLabel(provider: string): string {
  const normalized = provider.trim().toLowerCase().replaceAll("-", "_");
  if (normalized === "ollama") {
    return "Ollama";
  }
  if (normalized === "vllm") {
    return "vLLM";
  }
  if (normalized === "llama_cpp" || normalized === "llamacpp") {
    return "llama.cpp";
  }
  if (!normalized) {
    return "Unknown";
  }
  return provider.trim();
}

export function formatModeLabel(mode: string): string {
  return mode.replaceAll("_", " ").toUpperCase();
}

export function formatReasoningLabel(reasoning: string): string {
  return reasoning.replaceAll("_", " ");
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
  if (error || (!status && !loading)) {
    return "error";
  }
  if (!status) {
    return loading ? "degraded" : "error";
  }
  if (status.last_probe_error) {
    return "error";
  }
  if (status.degraded_state || transition?.is_transition) {
    return "degraded";
  }
  if (loading) {
    return "degraded";
  }
  return "healthy";
}

export function buildIntelligenceTooltip(
  status: AdaptiveIntelligenceStatus,
  transitionSummary: AdaptiveTransitionSummary | null,
): string {
  const lines = [
    `Tier: ${formatTierLabel(status.tier)} (${status.tier})`,
    `Model: ${status.recommended_model}`,
    `Backend: ${formatProviderLabel(status.recommended_provider)}`,
    `Mode: ${formatModeLabel(status.mode)}`,
    `Reasoning: ${formatReasoningLabel(status.reasoning_mode)}`,
    `Context: ${status.context_length.toLocaleString()}`,
  ];
  if (status.degraded_state && status.status_reason) {
    lines.push(`Degraded: ${status.status_reason}`);
  }
  if (status.last_probe_error) {
    lines.push(`Probe error: ${status.last_probe_error}`);
  }
  if (transitionSummary?.is_transition && transitionSummary.changed_fields.length > 0) {
    lines.push(`Transition: ${transitionSummary.changed_fields.join(", ")}`);
  }
  return lines.join("\n");
}
