import { describe, expect, it } from "vitest";

import {
  activationStepIndex,
  needsOperatorDecision,
  resolveBirthOperatorMode,
  shouldHideActivateForDecision,
  shouldShowDecisionBanner,
} from "@/lib/birthOperatorMode";
import type { BirthStatusPayload } from "@/lib/birthClient";

function status(partial: Partial<BirthStatusPayload>): BirthStatusPayload {
  return { status: "idle", ...partial };
}

describe("resolveBirthOperatorMode", () => {
  it("prioritizes launching while activating", () => {
    expect(
      resolveBirthOperatorMode({
        status: status({
          status: "interrupted",
          progress: { stage: "paused", phase: "paused", user_initiated_stop: true },
          checkpoint_resumable: true,
        }),
        activating: true,
        runPinned: false,
        genesisPinned: false,
        uiPhase: "idle",
      }),
    ).toBe("launching");
  });

  it("keeps training shell while runPinned (cold start)", () => {
    expect(
      resolveBirthOperatorMode({
        status: status({ status: "interrupted", live: false }),
        activating: false,
        runPinned: true,
        genesisPinned: false,
        uiPhase: "running",
      }),
    ).toBe("training");
  });

  it("maps interrupted without engine to decision", () => {
    expect(
      resolveBirthOperatorMode({
        status: status({
          status: "paused",
          progress: { stage: "paused", phase: "paused" },
          checkpoint_resumable: false,
        }),
        activating: false,
        runPinned: false,
        genesisPinned: false,
        uiPhase: "idle",
      }),
    ).toBe("decision");
  });

  it("maps clean idle to idle", () => {
    expect(
      resolveBirthOperatorMode({
        status: status({ status: "idle", progress: { stage: "not_started" } }),
        activating: false,
        runPinned: false,
        genesisPinned: false,
        uiPhase: "idle",
      }),
    ).toBe("idle");
  });

  it("maps live engine to training", () => {
    expect(
      resolveBirthOperatorMode({
        status: status({ status: "running", live: true }),
        activating: false,
        runPinned: false,
        genesisPinned: false,
        uiPhase: "running",
      }),
    ).toBe("training");
  });

  it("maps certificate failed to certificate_overlay", () => {
    expect(
      resolveBirthOperatorMode({
        status: status({ status: "certificate_failed" }),
        activating: false,
        runPinned: false,
        genesisPinned: false,
        uiPhase: "certificate_failed",
      }),
    ).toBe("certificate_overlay");
  });

  it("maps stage stalled to stall_overlay", () => {
    expect(
      resolveBirthOperatorMode({
        status: status({ status: "stage_stalled", progress: { stage: "stage_stalled" } }),
        activating: false,
        runPinned: false,
        genesisPinned: false,
        uiPhase: "stage_stalled",
      }),
    ).toBe("stall_overlay");
  });

  it("maps error uiPhase without live engine to decision (no orphan)", () => {
    expect(
      resolveBirthOperatorMode({
        status: status({ status: "error", message: "history failed" }),
        activating: false,
        runPinned: false,
        genesisPinned: false,
        uiPhase: "error",
      }),
    ).toBe("decision");
  });
});

describe("needsOperatorDecision", () => {
  it("is true for interrupted without live runner", () => {
    expect(
      needsOperatorDecision(
        status({
          status: "interrupted",
          progress: { user_initiated_stop: true, stage: "paused" },
        }),
      ),
    ).toBe(true);
  });

  it("is true for checkpoint resumable idle", () => {
    expect(
      needsOperatorDecision(
        status({ status: "idle", live: false, checkpoint_resumable: true }),
      ),
    ).toBe(true);
  });

  it("is false when engine is running", () => {
    expect(needsOperatorDecision(status({ status: "running", live: true }))).toBe(false);
  });
});

describe("activationStepIndex", () => {
  it("orders launch steps", () => {
    expect(activationStepIndex("fabric")).toBe(0);
    expect(activationStepIndex("twin")).toBe(1);
    expect(activationStepIndex("history")).toBe(2);
    expect(activationStepIndex("engine")).toBe(3);
    expect(activationStepIndex("done")).toBe(4);
  });
});

describe("shouldHideActivateForDecision", () => {
  it("hides Activate when interrupted or checkpoint", () => {
    expect(
      shouldHideActivateForDecision({
        sessionInterrupted: true,
        checkpointAvailable: false,
      }),
    ).toBe(true);
    expect(
      shouldHideActivateForDecision({
        sessionInterrupted: false,
        checkpointAvailable: true,
      }),
    ).toBe(true);
  });

  it("keeps Activate for residual history (Retry path)", () => {
    expect(
      shouldHideActivateForDecision({
        sessionInterrupted: false,
        checkpointAvailable: false,
      }),
    ).toBe(false);
  });

  it("never hides while activating", () => {
    expect(
      shouldHideActivateForDecision({
        sessionInterrupted: true,
        checkpointAvailable: true,
        activating: true,
      }),
    ).toBe(false);
  });
});

describe("shouldShowDecisionBanner", () => {
  it("shows for stop/checkpoint only", () => {
    expect(
      shouldShowDecisionBanner({ sessionInterrupted: true, checkpointAvailable: false }),
    ).toBe(true);
    expect(
      shouldShowDecisionBanner({ sessionInterrupted: false, checkpointAvailable: false }),
    ).toBe(false);
  });
});
