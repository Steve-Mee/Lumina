import { describe, expect, it } from "vitest";

import { playgroundSealBlocker } from "@/components/config/botConfigEnvelope";
import { defaultBotConfigDraft } from "@/lib/botConfigDraft";

describe("playgroundSealBlocker", () => {
  it("names the missing negative floor", () => {
    const draft = defaultBotConfigDraft();
    expect(playgroundSealBlocker(draft)).toBe("Daily loss cap must be a negative floor.");
  });

  it("allows a SIM floor and a positive open risk", () => {
    const draft = defaultBotConfigDraft();
    draft.risk.daily_loss_cap = -150;
    draft.risk.max_total_open_risk = 3000;
    expect(playgroundSealBlocker(draft)).toBeNull();
  });

  it("refuses REAL", () => {
    const draft = defaultBotConfigDraft();
    draft.mode = "real";
    draft.risk.daily_loss_cap = -150;
    expect(playgroundSealBlocker(draft)).toBe("Playground seal is SIM only.");
  });
});
