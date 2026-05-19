import { describe, expect, it } from "vitest";

import type { BirthStatusPayload } from "@/lib/birthClient";
import {
  checkpointTradeCount,
  detectBirthRecoveryKind,
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
