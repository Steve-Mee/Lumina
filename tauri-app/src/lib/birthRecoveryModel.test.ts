import { describe, expect, it } from "vitest";

import type { BirthStatusPayload } from "@/lib/birthClient";
import {
  detectBirthRecoveryKind,
  shouldAutoResumeBirth,
  verifyBirthWipeSucceeded,
} from "@/lib/birthRecoveryModel";

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

  it("does not auto-resume interrupted sessions — operator chooses Resume/Wipe", () => {
    expect(
      shouldAutoResumeBirth({
        status: "interrupted",
        live: false,
        checkpoint_resumable: true,
        progress: { stage: "paused", user_initiated_stop: true },
      } as BirthStatusPayload),
    ).toBe(false);
  });

  it("detects checkpoint recovery when resumable and not live", () => {
    expect(
      detectBirthRecoveryKind({
        status: "idle",
        live: false,
        checkpoint_resumable: true,
        progress: { stage: "training_running", phase: "curriculum_learning" },
      } as BirthStatusPayload),
    ).toBe("checkpoint_available");
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
