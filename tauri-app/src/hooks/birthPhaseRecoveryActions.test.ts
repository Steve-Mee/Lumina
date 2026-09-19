import { describe, expect, it, vi } from "vitest";

import { buildStalledRecoveryActions } from "@/hooks/birthPhaseRecoveryActions";

const handlers = {
  openWipeConfirm: vi.fn(),
  handleReviewGenesisSettings: vi.fn(),
  handleCopyForensicsCommand: vi.fn(),
  handleExpandAndRetryStalledStage: vi.fn(),
  handleResumeStalledStage: vi.fn(),
  handleAcceptChampion: vi.fn(),
  setRecoveryDismissed: vi.fn(),
};

describe("buildStalledRecoveryActions", () => {
  it("champion freeze only offers accept or wipe", () => {
    const actions = buildStalledRecoveryActions(false, handlers, { championFreeze: true });
    expect(actions.map((a) => a.id)).toEqual(["accept_champion", "wipe_full", "forensics"]);
    expect(actions.some((a) => a.id === "expand" || a.id === "retry")).toBe(false);
  });

  it("occupancy fencepost offers retry stage, not expand or accept", () => {
    const actions = buildStalledRecoveryActions(false, handlers, {
      championFreeze: true,
      retryStage: true,
    });
    expect(actions.map((a) => a.id)).toEqual(["retry", "wipe_full", "forensics"]);
    expect(actions.some((a) => a.id === "expand" || a.id === "accept_champion")).toBe(false);
  });

  it("non-freeze stall still offers expand and retry", () => {
    const actions = buildStalledRecoveryActions(false, handlers);
    expect(actions.map((a) => a.id)).toContain("expand");
    expect(actions.map((a) => a.id)).toContain("retry");
    expect(actions.map((a) => a.id)).not.toContain("accept_champion");
  });
});
