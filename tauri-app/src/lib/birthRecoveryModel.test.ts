import { describe, expect, it } from "vitest";

import type { BirthStatusPayload } from "@/lib/birthClient";
import { shouldAutoResumeBirth, verifyBirthWipeSucceeded } from "@/lib/birthRecoveryModel";

describe("verifyBirthWipeSucceeded", () => {
  it("accepts stale running poll when API already confirmed wipe", () => {
    const result = verifyBirthWipeSucceeded({
      apiStatus: "wiped",
      apiCheckpointResumable: false,
      polledStatus: {
        status: "running",
        checkpoint_resumable: false,
      } as BirthStatusPayload,
    });
    expect(result.ok).toBe(true);
  });

  it("auto-resumes phoenix_cycle stalls when retryable", () => {
    const ok = shouldAutoResumeBirth({
      status: "stage_stalled",
      progress: {
        phase: "stage_stalled",
        terminal_stall_reason: "phoenix_cycle",
        retryable: true,
        needs_attention: false,
      },
    } as BirthStatusPayload);
    expect(ok).toBe(true);
  });

  it("rejects when checkpoint remains resumable after wipe", () => {
    const result = verifyBirthWipeSucceeded({
      apiStatus: "wiped",
      apiCheckpointResumable: false,
      polledStatus: {
        status: "idle",
        checkpoint_resumable: true,
      } as BirthStatusPayload,
    });
    expect(result.ok).toBe(false);
  });
});
