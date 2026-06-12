import { describe, expect, it } from "vitest";

import type { BirthStatusPayload } from "@/lib/birthClient";
import {
  checkpointTradeCount,
  detectBirthRecoveryKind,
  shouldAutoResumeBirth,
} from "@/lib/birthRecoveryModel";

describe("birthRecoveryModel", () => {
  it("detects history_unavailable from stage or phase", () => {
    expect(
      detectBirthRecoveryKind({
        status: "running",
        progress: { stage: "history_unavailable" },
      } as BirthStatusPayload),
    ).toBe("history_unavailable");
    expect(
      detectBirthRecoveryKind({
        status: "running",
        progress: { phase: "loading_history_failed" },
      } as BirthStatusPayload),
    ).toBe("history_unavailable");
  });

  it("detects checkpoint_available", () => {
    expect(
      detectBirthRecoveryKind({
        status: "running",
        progress: { stage: "checkpoint_available", checkpoint_trades: 1200 },
      } as BirthStatusPayload),
    ).toBe("checkpoint_available");
  });

  it("detects simulation_stall phases", () => {
    expect(
      detectBirthRecoveryKind({
        status: "running",
        progress: { phase: "simulation_stall" },
      } as BirthStatusPayload),
    ).toBe("simulation_stall");
  });

  it("detects session_interrupted from top-level status", () => {
    expect(
      detectBirthRecoveryKind({
        status: "interrupted",
        progress: { stage: "interrupted", trades_done: 1200 },
      } as BirthStatusPayload),
    ).toBe("session_interrupted");
  });

  it("shouldAutoResumeBirth for interrupted and birth_interrupted reason", () => {
    const interrupted = {
      status: "interrupted",
      progress: { trades_done: 500 },
    } as BirthStatusPayload;
    expect(shouldAutoResumeBirth(interrupted)).toBe(true);
    expect(shouldAutoResumeBirth({ status: "idle" } as BirthStatusPayload, "birth_interrupted")).toBe(
      true,
    );
    expect(shouldAutoResumeBirth({ status: "idle" } as BirthStatusPayload, "birth_pending")).toBe(
      false,
    );
    expect(shouldAutoResumeBirth({ status: "running" } as BirthStatusPayload)).toBe(false);
  });

  it("returns null when no recovery stage", () => {
    expect(
      detectBirthRecoveryKind({
        status: "running",
        progress: { stage: "training", phase: "ppo" },
      } as BirthStatusPayload),
    ).toBeNull();
  });

  it("reads checkpoint trade count from progress", () => {
    expect(
      checkpointTradeCount({
        checkpoint_trades: 5000,
      } as BirthStatusPayload["progress"]),
    ).toBe(5000);
  });
});
