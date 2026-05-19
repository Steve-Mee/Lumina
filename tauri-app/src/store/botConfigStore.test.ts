import { beforeEach, describe, expect, it, vi } from "vitest";

import { defaultBotConfigDraft } from "@/lib/botConfigDraft";
import { useBotConfigStore } from "@/store/botConfigStore";

vi.mock("@/lib/setupClient", () => ({
  fetchOnboardingStatus: vi.fn(),
  postBotConfig: vi.fn(),
}));

import { fetchOnboardingStatus, postBotConfig } from "@/lib/setupClient";

describe("botConfigStore", () => {
  beforeEach(() => {
    useBotConfigStore.setState({
      draft: defaultBotConfigDraft(),
      baseline: defaultBotConfigDraft(),
      loading: false,
      saving: false,
      error: null,
    });
    vi.mocked(fetchOnboardingStatus).mockReset();
    vi.mocked(postBotConfig).mockReset();
  });

  it("marks dirty after draft update", () => {
    expect(useBotConfigStore.getState().isDirty()).toBe(false);
    useBotConfigStore.getState().updateDraft({
      risk: { ...defaultBotConfigDraft().risk, kelly_fraction: 0.4 },
    });
    expect(useBotConfigStore.getState().isDirty()).toBe(true);
  });

  it("save refreshes baseline from server defaults", async () => {
    vi.mocked(postBotConfig).mockResolvedValue({
      success: true,
      defaults: {
        mode: "sim",
        sim: { kelly_fraction: 0.55, max_mutation_depth: "moderate" },
        real: { kelly_fraction: 0.25, max_mutation_depth: "conservative" },
        evolution: {},
        first_boot: {},
        risk_controller: { real_capital_safety_threshold_usd: 1000, max_total_open_risk: 3000 },
      },
    });

    useBotConfigStore.getState().updateDraft({
      risk: { ...defaultBotConfigDraft().risk, kelly_fraction: 0.55 },
      evolution: {
        ...defaultBotConfigDraft().evolution,
        max_mutation_depth: "moderate",
      },
    });

    const ok = await useBotConfigStore.getState().save();
    expect(ok).toBe(true);
    expect(useBotConfigStore.getState().isDirty()).toBe(false);
    expect(useBotConfigStore.getState().draft.risk.kelly_fraction).toBe(0.55);
  });
});
