import { describe, expect, it } from "vitest";

import type { BirthStatusPayload } from "@/lib/birthClient";
import { computeBirthApplyStatusPatch } from "@/store/birthStoreApplyStatus";

function patch(payload: BirthStatusPayload, uiPhase: "finale" | "idle" = "finale", genesisPinned = false) {
  return computeBirthApplyStatusPatch(payload, {
    uiPhase,
    runPinned: false,
    genesisPinned,
    birthSurface: "running",
  });
}

describe("computeBirthApplyStatusPatch finale after wipe", () => {
  it("drops a sticky finale when Birth exit is closed", () => {
    const next = patch({ status: "idle", birth_exit_ok: false, live: false });
    expect(next.uiPhase).toBe("idle");
    expect(next.birthSurface).toBe("genesis");
  });

  it("does not re-enter finale while Genesis is pinned", () => {
    const next = patch(
      {
        status: "completed",
        birth_exit_ok: true,
        artifacts_ok: true,
        progress: { stage: "completed" },
      },
      "idle",
      true,
    );
    expect(next.uiPhase).toBe("idle");
    expect(next.birthSurface).toBe("genesis");
  });

  it("keeps finale when Birth has actually exited and Genesis is not pinned", () => {
    const next = patch({
      status: "completed",
      birth_exit_ok: true,
      artifacts_ok: true,
      progress: { stage: "completed" },
    });
    expect(next.uiPhase).toBe("finale");
  });
});
