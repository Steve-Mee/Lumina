import { describe, expect, it } from "vitest";

import type { BirthStatusPayload } from "@/lib/birthClient";
import {
  detectBirthRecoveryKind,
  readBirthRecoveryCompress,
  recoveryOperatorHint,
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

  it("reads H6 compressed recovery and surfaces theater hint", () => {
    const status = {
      status: "stage_stalled",
      progress: {
        recovery: {
          schema: "recovery_compress_v1",
          active: "plateau",
          theater: true,
          next_action: "stop_auto_recovery_expand_or_manual",
        },
      },
    } as BirthStatusPayload;
    expect(readBirthRecoveryCompress(status)?.active).toBe("plateau");
    expect(recoveryOperatorHint(status)).toContain("theater");
  });
});
