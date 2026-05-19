import { describe, expect, it } from "vitest";

import { filterAdaptiveHistoryEvents } from "@/lib/adaptiveIntelligenceTypes";

describe("AdaptiveIntelligenceHistoryPanel filter", () => {
  it("matches provider and status reason text", () => {
    const events = [
      {
        timestamp: "2026-05-19T12:00:00Z",
        payload: {
          tier: "standard",
          mode: "auto",
          recommended_model: "qwen2.5:7b",
          recommended_provider: "vllm",
          status_reason: "gpu memory pressure",
        },
      },
    ];
    expect(filterAdaptiveHistoryEvents(events, "vllm")).toHaveLength(1);
    expect(filterAdaptiveHistoryEvents(events, "memory")).toHaveLength(1);
    expect(filterAdaptiveHistoryEvents(events, "missing")).toHaveLength(0);
  });
});
