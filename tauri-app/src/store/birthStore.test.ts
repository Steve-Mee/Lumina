import { describe, expect, it, vi, beforeEach } from "vitest";

import type { BirthStatusPayload } from "@/lib/birthClient";
import { useBirthStore } from "@/store/birthStore";

vi.mock("@/lib/birthClient", () => ({
  fetchBirthStatusTyped: vi.fn(),
  isBirthStartSuccessful: (status: unknown) =>
    String(status ?? "").toLowerCase() === "started",
  resumeStalledStageSession: vi.fn(),
  expandAndRetryStalledStageSession: vi.fn(),
  retryBirthSession: vi.fn(),
  resumeBirthSession: vi.fn(),
  reuseDataBirthSession: vi.fn(),
  startBirthSessionContinue: vi.fn(),
}));

const stageStalledStatus = {
  status: "stage_stalled",
  progress: { phase: "stage_stalled", pass_reason: "winrate 26.9% < 45%" },
} as BirthStatusPayload;

describe("birthStore stage_stalled recovery", () => {
  beforeEach(() => {
    useBirthStore.getState().reset();
  });

  it("maps stage_stalled status to uiPhase stage_stalled", () => {
    useBirthStore.getState().applyStatus(stageStalledStatus);
    expect(useBirthStore.getState().uiPhase).toBe("stage_stalled");
  });

  it("keeps stage_stalled uiPhase on resumeStalledStage failure", async () => {
    const { resumeStalledStageSession } = await import("@/lib/birthClient");
    vi.mocked(resumeStalledStageSession).mockRejectedValueOnce(new Error("network"));

    const ok = await useBirthStore.getState().resumeStalledStage();
    expect(ok).toBe(false);
    expect(useBirthStore.getState().uiPhase).toBe("stage_stalled");
  });
});
