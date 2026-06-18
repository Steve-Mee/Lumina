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

  it("detects stage_stalled from top-level status", () => {
    expect(
      detectBirthRecoveryKind({
        status: "stage_stalled",
        progress: { pass_reason: "winrate 13.0% < 45%" },
      } as BirthStatusPayload),
    ).toBe("stage_stalled");
  });

  it("detects stage_stalled from progress phase only", () => {
    expect(
      detectBirthRecoveryKind({
        status: "idle",
        progress: {
          stage: "stage_stalled",
          phase: "stage_stalled",
          pass_reason: "winrate 13.0% < 45%",
        },
      } as BirthStatusPayload),
    ).toBe("stage_stalled");
  });

  it("prefers certificate_failed over progress stage_stalled when top-level cert fail", () => {
    expect(
      detectBirthRecoveryKind({
        status: "certificate_failed",
        progress: { phase: "stage_stalled" },
      } as BirthStatusPayload),
    ).toBe("certificate_failed");
  });

  it("detects certificate_failed from progress phase", () => {
    expect(
      detectBirthRecoveryKind({
        status: "idle",
        progress: { phase: "certificate_failed", failure_reasons: ["oos_sharpe:0.1/0.35"] },
      } as BirthStatusPayload),
    ).toBe("certificate_failed");
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
