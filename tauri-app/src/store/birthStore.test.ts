import { describe, expect, it, vi, beforeEach } from "vitest";

import type { BirthStatusPayload } from "@/lib/birthClient";
import {
  isBirthPollInFlight,
  isTransientHeavyBirthPhase,
  isTransientPollWarning,
  TRANSIENT_POLL_WARNING,
  useBirthStore,
} from "@/store/birthStore";

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
  stopBirthSession: vi.fn(),
  wipeAllBirthData: vi.fn(),
}));

vi.mock("@/lib/runtimeClient", () => ({
  stopBirth: vi.fn(),
}));

const stageStalledStatus = {
  status: "stage_stalled",
  progress: { phase: "stage_stalled", pass_reason: "winrate 26.9% < 45%" },
} as BirthStatusPayload;

describe("birthStore stage_stalled recovery", () => {
  beforeEach(async () => {
    useBirthStore.getState().reset();
    const { fetchBirthStatusTyped } = await import("@/lib/birthClient");
    vi.mocked(fetchBirthStatusTyped).mockReset();
  });

  it("maps stage_stalled status to uiPhase stage_stalled and recovery surface", () => {
    useBirthStore.getState().applyStatus(stageStalledStatus);
    expect(useBirthStore.getState().uiPhase).toBe("stage_stalled");
    expect(useBirthStore.getState().birthSurface).toBe("recovery");
  });

  it("maps live detected progress to running surface even when top status is idle", () => {
    useBirthStore.getState().applyStatus({
      status: "idle",
      live: true,
      certificate_ok: false,
      progress: { stage: "detected", phase: "detected" },
    } as BirthStatusPayload);
    expect(useBirthStore.getState().uiPhase).toBe("running");
    expect(useBirthStore.getState().birthSurface).toBe("running");
  });

  it("keeps orphaned disk progress on genesis so Resume/Wipe stays available", () => {
    useBirthStore.getState().applyStatus({
      status: "idle",
      live: false,
      certificate_ok: false,
      checkpoint_resumable: true,
      progress: { stage: "training_running", phase: "curriculum_learning" },
    } as BirthStatusPayload);
    expect(useBirthStore.getState().uiPhase).not.toBe("running");
    expect(useBirthStore.getState().birthSurface).toBe("genesis");
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

  it("stopBirthRun pins genesis when poll confirms engine stopped", async () => {
    const { fetchBirthStatusTyped, stopBirthSession } = await import("@/lib/birthClient");

    vi.mocked(stopBirthSession).mockResolvedValueOnce({ status: "stopped" });
    vi.mocked(fetchBirthStatusTyped)
      .mockResolvedValueOnce({
        status: "running",
        live: true,
        progress: { stage: "curriculum_stage", phase: "ppo_training" },
      } as BirthStatusPayload)
      .mockResolvedValue({
        status: "idle",
        live: false,
        progress: { stage: "interrupted", user_initiated_stop: true },
      } as BirthStatusPayload);

    useBirthStore.getState().beginBirthRun();
    const ok = await useBirthStore.getState().stopBirthRun();

    expect(ok).toBe(true);
    expect(useBirthStore.getState().uiPhase).toBe("idle");
    expect(useBirthStore.getState().birthSurface).toBe("genesis");
    expect(useBirthStore.getState().genesisPinned).toBe(true);
  });

  it("stopBirthRun does not pin genesis when engine stays live", async () => {
    vi.useFakeTimers();
    try {
      const { fetchBirthStatusTyped, stopBirthSession } = await import("@/lib/birthClient");

      vi.mocked(stopBirthSession).mockResolvedValueOnce({ status: "stopping" });
      vi.mocked(fetchBirthStatusTyped).mockResolvedValue({
        status: "running",
        live: true,
        progress: { stage: "curriculum_stage", phase: "ppo_training" },
      } as BirthStatusPayload);

      useBirthStore.getState().beginBirthRun();
      const stopPromise = useBirthStore.getState().stopBirthRun();
      await vi.advanceTimersByTimeAsync(35_000);
      const ok = await stopPromise;

      expect(ok).toBe(false);
      expect(useBirthStore.getState().genesisPinned).toBe(false);
      expect(useBirthStore.getState().pollError).toMatch(/engine/i);
    } finally {
      vi.useRealTimers();
    }
  });

  it("runPinned keeps running surface during interrupted cold-start polls", () => {
    useBirthStore.getState().beginBirthRun();
    expect(useBirthStore.getState().runPinned).toBe(true);
    expect(useBirthStore.getState().birthSurface).toBe("running");

    useBirthStore.getState().applyStatus({
      status: "interrupted",
      live: false,
      progress: { stage: "interrupted", phase: "paused" },
    } as BirthStatusPayload);

    expect(useBirthStore.getState().uiPhase).toBe("running");
    expect(useBirthStore.getState().birthSurface).toBe("running");
    expect(useBirthStore.getState().runPinned).toBe(true);
  });

  it("runPinned clears when engine becomes live", () => {
    useBirthStore.getState().beginBirthRun();
    useBirthStore.getState().applyStatus({
      status: "running",
      live: true,
      progress: { stage: "training_running", phase: "ppo_training" },
    } as BirthStatusPayload);
    expect(useBirthStore.getState().birthSurface).toBe("running");
    expect(useBirthStore.getState().runPinned).toBe(false);
  });

  it("bootstrapSession respects genesisPinned and does not force running surface", async () => {
    const { fetchBirthStatusTyped } = await import("@/lib/birthClient");
    vi.mocked(fetchBirthStatusTyped).mockResolvedValueOnce({
      status: "running",
      progress: { stage: "training_running", phase: "ppo_training" },
    } as BirthStatusPayload);

    useBirthStore.setState({ genesisPinned: true, uiPhase: "idle", birthSurface: "genesis" });
    const ok = await useBirthStore.getState().bootstrapSession({
      targetTrades: 25000,
    });

    expect(ok).toBe(false);
    expect(useBirthStore.getState().birthSurface).toBe("genesis");
    expect(useBirthStore.getState().uiPhase).toBe("idle");
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

  it("returnToGenesis pins genesis surface and clears certificate overlay uiPhase", () => {
    useBirthStore.getState().applyStatus({
      status: "certificate_failed",
      certificate_ok: false,
      progress: { stage: "failed", phase: "certificate_failed" },
    } as BirthStatusPayload);
    expect(useBirthStore.getState().uiPhase).toBe("certificate_failed");

    useBirthStore.getState().returnToGenesis();

    expect(useBirthStore.getState().uiPhase).toBe("idle");
    expect(useBirthStore.getState().birthSurface).toBe("genesis");
    expect(useBirthStore.getState().genesisPinned).toBe(true);
  });

  it("returnToGenesis keeps genesis surface when backend still reports stage_stalled", () => {
    useBirthStore.getState().applyStatus(stageStalledStatus);
    expect(useBirthStore.getState().uiPhase).toBe("stage_stalled");
    expect(useBirthStore.getState().birthSurface).toBe("recovery");

    useBirthStore.getState().returnToGenesis();
    expect(useBirthStore.getState().uiPhase).toBe("idle");
    expect(useBirthStore.getState().birthSurface).toBe("genesis");
    expect(useBirthStore.getState().genesisPinned).toBe(true);

    useBirthStore.getState().applyStatus(stageStalledStatus);
    expect(useBirthStore.getState().uiPhase).toBe("idle");
    expect(useBirthStore.getState().birthSurface).toBe("genesis");
    expect(useBirthStore.getState().genesisPinned).toBe(true);
  });

  it("returnToGenesis stays on genesis when backend still reports error (PPO/fail)", () => {
    useBirthStore.getState().applyStatus({
      status: "error",
      error: "PPO trainer unbound or incompatible (missing create_fresh_birth_policy)",
      message: "Birth Phase gefaald",
      live: false,
    } as BirthStatusPayload);
    expect(useBirthStore.getState().uiPhase).toBe("error");

    useBirthStore.getState().returnToGenesis();
    expect(useBirthStore.getState().uiPhase).toBe("idle");
    expect(useBirthStore.getState().birthSurface).toBe("genesis");
    expect(useBirthStore.getState().genesisPinned).toBe(true);

    // Poll re-applies same error payload — must not yank operator off Genesis.
    useBirthStore.getState().applyStatus({
      status: "error",
      error: "PPO trainer unbound or incompatible (missing create_fresh_birth_policy)",
      message: "Birth Phase gefaald",
      live: false,
    } as BirthStatusPayload);
    expect(useBirthStore.getState().uiPhase).toBe("idle");
    expect(useBirthStore.getState().birthSurface).toBe("genesis");
    expect(useBirthStore.getState().genesisPinned).toBe(true);
  });

  it("idle not_started maps to genesis surface after applyStatus", () => {
    useBirthStore.getState().applyStatus({
      status: "idle",
      certificate_ok: false,
      progress: { stage: "not_started" },
    } as BirthStatusPayload);
    expect(useBirthStore.getState().uiPhase).toBe("idle");
    expect(useBirthStore.getState().birthSurface).toBe("genesis");
  });

  it("applyStatus prioritizes running uiPhase when engine is live despite stale stall progress", () => {
    useBirthStore.getState().beginBirthRun();
    useBirthStore.getState().applyStatus({
      status: "running",
      live: true,
      progress: { phase: "stage_stalled", stage: "loading_data" },
    } as BirthStatusPayload);

    expect(useBirthStore.getState().uiPhase).toBe("running");
    expect(useBirthStore.getState().birthSurface).toBe("running");
  });

  it("detects transient heavy birth phases during regime map build", () => {
    expect(
      isTransientHeavyBirthPhase({
        status: "running",
        progress: { stage: "loading_data", phase: "enriching_regimes" },
      } as BirthStatusPayload),
    ).toBe(true);
    expect(
      isTransientHeavyBirthPhase({
        status: "running",
        progress: { stage: "training_running", phase: "curriculum_stage" },
      } as BirthStatusPayload),
    ).toBe(false);
  });

  it("suppresses pollError for transient failures until the third consecutive miss", async () => {
    const { fetchBirthStatusTyped } = await import("@/lib/birthClient");
    useBirthStore.getState().applyStatus({
      status: "running",
      progress: { stage: "loading_data", phase: "enriching_regimes" },
    } as BirthStatusPayload);

    vi.mocked(fetchBirthStatusTyped).mockRejectedValue("connection lost");

    await useBirthStore.getState().poll();
    expect(useBirthStore.getState().pollError).toBeNull();

    await useBirthStore.getState().poll();
    expect(useBirthStore.getState().pollError).toBeNull();

    await useBirthStore.getState().poll();
    expect(useBirthStore.getState().pollError).toBe(TRANSIENT_POLL_WARNING);
    expect(isTransientPollWarning(useBirthStore.getState().pollError)).toBe(true);
  });

  it("surfaces non-transient poll failures immediately", async () => {
    const { fetchBirthStatusTyped } = await import("@/lib/birthClient");
    useBirthStore.getState().applyStatus({
      status: "idle",
      progress: { stage: "not_started" },
    } as BirthStatusPayload);

    vi.mocked(fetchBirthStatusTyped).mockRejectedValueOnce(new Error("HTTP 503"));

    await useBirthStore.getState().poll();
    expect(useBirthStore.getState().pollError).toBe("HTTP 503");
  });

  it("pollFresh waits for in-flight poll then fetches updated status", async () => {
    const { fetchBirthStatusTyped } = await import("@/lib/birthClient");
    let resolveFirst!: (value: BirthStatusPayload) => void;
    const firstPromise = new Promise<BirthStatusPayload>((resolve) => {
      resolveFirst = resolve;
    });

    vi.mocked(fetchBirthStatusTyped)
      .mockImplementationOnce(() => firstPromise)
      .mockResolvedValueOnce({
        status: "idle",
        checkpoint_resumable: false,
        progress: { stage: "not_started" },
      } as BirthStatusPayload);

    const inFlightPoll = useBirthStore.getState().poll();
    expect(isBirthPollInFlight()).toBe(true);

    const freshPromise = useBirthStore.getState().pollFresh();
    resolveFirst({
      status: "interrupted",
      checkpoint_resumable: true,
      progress: { stage: "interrupted" },
    } as BirthStatusPayload);
    await inFlightPoll;

    const fresh = await freshPromise;
    expect(fresh?.status).toBe("idle");
    expect(vi.mocked(fetchBirthStatusTyped)).toHaveBeenCalledTimes(2);
  });
});
