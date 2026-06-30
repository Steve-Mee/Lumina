import { describe, expect, it } from "vitest";

import type { BirthStatusPayload } from "@/lib/birthClient";
import { shouldAutoResumeBirth } from "@/lib/birthRecoveryModel";

describe("shouldAutoResumeBirth", () => {
  it("skips auto-resume when user_initiated_stop is set", () => {
    const status = {
      status: "interrupted",
      progress: { stage: "interrupted", user_initiated_stop: true },
    } as BirthStatusPayload;
    expect(shouldAutoResumeBirth(status, "birth_interrupted")).toBe(false);
  });

  it("skips auto-resume when progress indicates active historical load", () => {
    const status = {
      status: "idle",
      progress: { stage: "loading_data", phase: "loading_history" },
    } as BirthStatusPayload;
    expect(shouldAutoResumeBirth(status)).toBe(false);
  });

  it("allows auto-resume for interrupted without user stop flag", () => {
    const status = {
      status: "interrupted",
      progress: { stage: "interrupted" },
    } as BirthStatusPayload;
    expect(shouldAutoResumeBirth(status, "birth_interrupted")).toBe(true);
  });

  it("allows auto-resume for retryable stage_stalled", () => {
    const status = {
      status: "stage_stalled",
      progress: {
        stage: "stage_stalled",
        phase: "stage_stalled",
        retryable: true,
      },
    } as BirthStatusPayload;
    expect(shouldAutoResumeBirth(status)).toBe(true);
  });

  it("skips auto-resume for stage_stalled when user stopped", () => {
    const status = {
      status: "stage_stalled",
      progress: {
        stage: "stage_stalled",
        phase: "stage_stalled",
        retryable: true,
        user_initiated_stop: true,
      },
    } as BirthStatusPayload;
    expect(shouldAutoResumeBirth(status)).toBe(false);
  });
});
