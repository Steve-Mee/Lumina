import { describe, expect, it } from "vitest";

import {
  filterAdaptiveHistoryEvents,
  normalizeAdaptiveIntelligenceStatus,
  normalizeTransitionSummary,
  resolveIntelligenceHealth,
} from "@/lib/adaptiveIntelligenceTypes";

describe("adaptiveIntelligenceTypes", () => {
  it("normalizes monitoring envelope payload", () => {
    const status = normalizeAdaptiveIntelligenceStatus({
      payload: {
        tier: "high",
        mode: "auto",
        reasoning_mode: "chain_of_thought",
        degraded_state: false,
        status_reason: "",
        recommended_model: "qwen2.5:14b",
        recommended_provider: "ollama",
        context_length: 8192,
        last_probe_error: null,
      },
    });
    expect(status?.tier).toBe("high");
    expect(status?.recommended_model).toBe("qwen2.5:14b");
  });

  it("resolves degraded health on probe error", () => {
    const status = normalizeAdaptiveIntelligenceStatus({
      tier: "light",
      mode: "auto",
      reasoning_mode: "fast",
      degraded_state: false,
      status_reason: "",
      recommended_model: "tiny",
      recommended_provider: "ollama",
      context_length: 2048,
      last_probe_error: "connection refused",
    });
    expect(resolveIntelligenceHealth({ status, loading: false, error: null })).toBe("error");
  });

  it("normalizes transition summary", () => {
    const summary = normalizeTransitionSummary({
      is_transition: true,
      changed_fields: ["tier"],
      from_state: { tier: "light", mode: "auto" },
      to_state: { tier: "standard", mode: "auto" },
    });
    expect(summary?.is_transition).toBe(true);
    expect(summary?.changed_fields).toEqual(["tier"]);
  });

  it("filters history by search query", () => {
    const events = [
      {
        timestamp: "2026-05-19T12:00:00Z",
        payload: { tier: "high", recommended_model: "qwen2.5:14b", mode: "auto" },
      },
      {
        timestamp: "2026-05-19T11:00:00Z",
        payload: { tier: "light", recommended_model: "phi3", mode: "force_light" },
      },
    ];
    expect(filterAdaptiveHistoryEvents(events, "phi3")).toHaveLength(1);
    expect(filterAdaptiveHistoryEvents(events, "")).toHaveLength(2);
  });
});
