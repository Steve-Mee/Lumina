import { describe, expect, it, vi, beforeEach } from "vitest";

import type { BirthStatusPayload } from "@/lib/birthClient";
import { useBirthStore } from "@/store/birthStore";

vi.mock("@/lib/birthClient", () => ({
  fetchBirthStatusTyped: vi.fn(),
  isBirthStartSuccessful: (status: unknown) =>
    String(status ?? "").toLowerCase() === "started",
  resumeStalledStageSession: vi.fn(),
  expandAndRetryStalledStageSession: vi.fn(),
  retryBirthSession: vi.fn(),
  resumeBirthSession: vi.fn(),
  reuseDataBirthSession: vi.fn(),
  startBirthSessionContinue: vi.fn(),
}));

vi.mock("@/lib/runtimeClient", () => ({
  stopBirth: vi.fn(),
}));

const stageStalledStatus = {
  status: "stage_stalled",
  progress: { phase: "stage_stalled", pass_reason: "winrate 26.9% < 45%" },
} as BirthStatusPayload;

describe("birthStore stage_stalled recovery", () => {
  beforeEach(() => {
    useBirthStore.getState().reset();
  });

  it("maps stage_stalled status to uiPhase stage_stalled and recovery surface", () => {
    useBirthStore.getState().applyStatus(stageStalledStatus);
    expect(useBirthStore.getState().uiPhase).toBe("stage_stalled");
    expect(useBirthStore.getState().birthSurface).toBe("recovery");
  });

  it("maps detected progress to running surface even when top status is idle", () => {
    useBirthStore.getState().applyStatus({
      status: "idle",
      certificate_ok: false,
      progress: { stage: "detected", phase: "detected" },
    } as BirthStatusPayload);
    expect(useBirthStore.getState().uiPhase).toBe("running");
    expect(useBirthStore.getState().birthSurface).toBe("running");
  });

  it("maps interrupted status to genesis surface via idle uiPhase", () => {
    useBirthStore.getState().setBirthSurface("running");
    useBirthStore.getState().applyStatus({
      status: "interrupted",
      progress: { stage: "interrupted", user_initiated_stop: true },
    } as BirthStatusPayload);
    expect(useBirthStore.getState().uiPhase).toBe("idle");
    expect(useBirthStore.getState().birthSurface).toBe("genesis");
  });

  it("maps running status to running surface", () => {
    useBirthStore.getState().applyStatus({
      status: "running",
      progress: { stage: "training_running", phase: "curriculum_stage" },
    } as BirthStatusPayload);
    expect(useBirthStore.getState().birthSurface).toBe("running");
  });

  it("keeps stage_stalled uiPhase on resumeStalledStage failure", async () => {
    const { resumeStalledStageSession } = await import("@/lib/birthClient");
    vi.mocked(resumeStalledStageSession).mockRejectedValueOnce(new Error("network"));

    const ok = await useBirthStore.getState().resumeStalledStage();
    expect(ok).toBe(false);
    expect(useBirthStore.getState().uiPhase).toBe("stage_stalled");
  });

  it("stopBirthRun returns to genesis while backend progress is still active", async () => {
    const { fetchBirthStatusTyped } = await import("@/lib/birthClient");
    const { stopBirth } = await import("@/lib/runtimeClient");

    vi.mocked(stopBirth).mockResolvedValueOnce({ status: "stopping" });
    vi.mocked(fetchBirthStatusTyped).mockResolvedValueOnce({
      status: "running",
      progress: { stage: "curriculum_stage", phase: "ppo_training" },
    } as BirthStatusPayload);

    useBirthStore.getState().beginBirthRun();
    const ok = await useBirthStore.getState().stopBirthRun();

    expect(ok).toBe(true);
    expect(useBirthStore.getState().uiPhase).toBe("idle");
    expect(useBirthStore.getState().birthSurface).toBe("genesis");
    expect(useBirthStore.getState().genesisPinned).toBe(true);
  });

  it("applyStatus keeps genesis surface when engine is still shutting down", () => {
    useBirthStore.setState({ uiPhase: "idle", birthSurface: "genesis", genesisPinned: true });
    useBirthStore.getState().applyStatus({
      status: "running",
      progress: { stage: "curriculum_stage", phase: "ppo_training" },
    } as BirthStatusPayload);

    expect(useBirthStore.getState().uiPhase).toBe("idle");
    expect(useBirthStore.getState().birthSurface).toBe("genesis");
    expect(useBirthStore.getState().genesisPinned).toBe(true);
  });
});
