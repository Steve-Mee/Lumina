import { describe, expect, it } from "vitest";

import { defaultBotConfigDraft, toBotConfigPayload } from "@/lib/botConfigDraft";

describe("botConfigDraft preferences", () => {
  it("includes runtime preferences in payload", () => {
    const draft = defaultBotConfigDraft();
    const payload = toBotConfigPayload(draft);
    expect(payload.preferences?.instrument).toBe("ES");
    expect(payload.preferences?.voice_enabled).toBe(true);
  });
});

describe("runtimeClient paths", () => {
  it("defines stop-all and training control paths", async () => {
    const mod = await import("@/lib/runtimeClient");
    expect(typeof mod.stopAllActivities).toBe("function");
    expect(typeof mod.pauseTraining).toBe("function");
    expect(typeof mod.resumeTraining).toBe("function");
    expect(typeof mod.goLiveReal).toBe("function");
  });
});

describe("opsClient reconciliation", () => {
  it("exports fetchReconciliationStatus", async () => {
    const mod = await import("@/lib/opsClient");
    expect(typeof mod.fetchReconciliationStatus).toBe("function");
  });
});
