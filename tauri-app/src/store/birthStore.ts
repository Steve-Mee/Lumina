import { create } from "zustand";

import type { BirthStatusPayload, BirthWipeResult } from "@/lib/birthClient";
import {
  acceptChampionSession,
  autonomousRecoverySession,
  expandAndRetryStalledStageSession,
  fetchBirthStatusTyped,
  isBirthStartSuccessful,
  resumeStalledStageSession,
  retryBirthSession,
  resumeBirthSession,
  reuseDataBirthSession,
  startBirthSessionContinue,
  stopBirthSession,
  wipeAllBirthData,
} from "@/lib/birthClient";
import {
  buildMilestones,
  isBirthComplete,
  isBirthCertificateFailed,
  isBirthEngineActive,
  isBirthFailed,
  isBirthInterrupted,
  isBirthStageStalled,
  resolveBirthHeadline,
  type BirthMilestone,
} from "@/lib/birthPhaseModel";
import { shouldAutoResumeBirth, verifyBirthWipeSucceeded } from "@/lib/birthRecoveryModel";
import { traceBirthWipe } from "@/lib/birthWipeTrace";
import {
  isBirthPollInFlight,
  isTransientHeavyBirthPhase,
  isTransientPollWarning,
  pollBirthStatusWithErrorHandling,
  pollFreshBirthStatus,
  resetPollCoordinator,
  TRANSIENT_POLL_WARNING,
  WIPE_VERIFY_ATTEMPTS,
  WIPE_VERIFY_DELAY_MS,
} from "@/store/birthPollCoordinator";
import {
  recoveryFailureUiPhase,
  resolveBirthSurface,
  type BirthSurface,
  type BirthUiPhase,
} from "@/store/birthSurfaceModel";

export {
  isBirthPollInFlight,
  isTransientHeavyBirthPhase,
  isTransientPollWarning,
  TRANSIENT_POLL_WARNING,
};
export type { BirthSurface, BirthUiPhase };

/** Cold-start probe for previous birth session (checkpoint / interrupted). */
export type BirthSessionProbeState = "pending" | "ready" | "error";

interface BirthState {
  status: BirthStatusPayload | null;
  milestones: BirthMilestone[];
  headline: string;
  uiPhase: BirthUiPhase;
  birthSurface: BirthSurface;
  genesisPinned: boolean;
  /** Sticky operator intent to stay on training shell during resume cold-start. */
  runPinned: boolean;
  pollError: string | null;
  /**
   * First successful status poll completed. Until true, Activate must stay
   * locked so operators cannot start a fresh birth over an unknown prior session.
   */
  sessionHydrated: boolean;
  sessionProbeState: BirthSessionProbeState;
  targetTrades: number;
  setTargetTrades: (n: number) => void;
  setBirthSurface: (surface: BirthSurface) => void;
  beginBirthRun: () => void;
  applyStatus: (payload: BirthStatusPayload) => void;
  markSessionProbeError: (message?: string | null) => void;
  poll: () => Promise<BirthStatusPayload | null>;
  pollFresh: () => Promise<BirthStatusPayload | null>;
  bootstrapSession: (context: {
    appSurfaceReason?: string;
    targetTrades: number;
  }) => Promise<boolean>;
  retryBirth: (options?: { wipe?: boolean }) => Promise<boolean>;
  resumeBirth: () => Promise<boolean>;
  acceptChampion: () => Promise<boolean>;
  resumeStalledStage: () => Promise<boolean>;
  expandAndRetryStalledStage: () => Promise<boolean>;
  executeRecommendedRecovery: () => Promise<boolean>;
  reuseDataBirth: () => Promise<boolean>;
  stopBirthRun: () => Promise<boolean>;
  wipeBirthData: (options?: { preserveTickCache?: boolean }) => Promise<BirthWipeResult>;
  returnToGenesis: () => void;
  beginFinale: () => void;
  reset: () => void;
}

export const useBirthStore = create<BirthState>((set, get) => ({
  status: null,
  milestones: buildMilestones(undefined, "idle"),
  headline: "Organism is being born…",
  uiPhase: "idle",
  birthSurface: "genesis",
  genesisPinned: false,
  runPinned: false,
  pollError: null,
  sessionHydrated: false,
  sessionProbeState: "pending",
  targetTrades: 25000,

  setTargetTrades: (n) => set({ targetTrades: n }),

  setBirthSurface: (surface) => set({ birthSurface: surface }),

  beginBirthRun: () =>
    set({
      uiPhase: "running",
      birthSurface: "running",
      genesisPinned: false,
      runPinned: true,
      pollError: null,
    }),

  applyStatus: (payload) => {
    const milestones = buildMilestones(payload.progress, payload.status);
    const headline = resolveBirthHeadline(
      milestones,
      payload.status,
      payload.progress,
      payload.certificate_ok,
    );
    let uiPhase: BirthUiPhase = get().uiPhase;
    let runPinned = get().runPinned;
    const genesisPinned = get().genesisPinned;

    const engineActive = payload.live === true || isBirthEngineActive(payload);

    if (get().uiPhase === "finale") {
      /* keep finale until parent transitions */
    } else if (runPinned && !genesisPinned) {
      // Raptor v14: keep training shell during cold-start; clear pin once live or terminal.
      if (engineActive) {
        uiPhase = "running";
        runPinned = false;
      } else if (isBirthComplete(payload)) {
        uiPhase = "finale";
        runPinned = false;
      } else if (isBirthStageStalled(payload)) {
        uiPhase = "stage_stalled";
        runPinned = false;
      } else if (isBirthCertificateFailed(payload)) {
        uiPhase = "certificate_failed";
        runPinned = false;
      } else if (isBirthFailed(payload) && !isBirthInterrupted(payload)) {
        uiPhase = "error";
        runPinned = false;
      } else {
        // interrupted / idle / starting → stay on running shell
        uiPhase = "running";
      }
    } else if (engineActive && !genesisPinned) {
      uiPhase = "running";
    } else if (isBirthCertificateFailed(payload)) {
      uiPhase = genesisPinned ? "idle" : "certificate_failed";
    } else if (isBirthComplete(payload)) {
      uiPhase = "finale";
    } else if (isBirthStageStalled(payload)) {
      uiPhase = genesisPinned ? "idle" : "stage_stalled";
    } else if (isBirthEngineActive(payload)) {
      uiPhase = genesisPinned ? "idle" : "running";
    } else if (isBirthFailed(payload)) {
      // Respect operator pin: Return to Genesis must not be overwritten by poll.
      uiPhase = genesisPinned ? "idle" : "error";
    } else if (isBirthInterrupted(payload)) {
      uiPhase = "idle";
    } else if (genesisPinned) {
      uiPhase = "idle";
    }

    const birthSurface = resolveBirthSurface(
      uiPhase,
      get().birthSurface,
      payload,
      genesisPinned,
      runPinned,
    );

    set({
      status: payload,
      milestones,
      headline,
      uiPhase,
      birthSurface,
      runPinned,
      pollError: null,
      sessionHydrated: true,
      sessionProbeState: "ready",
    });
  },

  markSessionProbeError: (message) =>
    set({
      sessionProbeState: "error",
      // Keep Activate locked until a successful status arrives.
      sessionHydrated: false,
      pollError:
        message?.trim() ||
        "Could not load birth session status. Retry before activating a new birth.",
    }),

  poll: async () =>
    pollBirthStatusWithErrorHandling(
      (payload) => get().applyStatus(payload),
      () => get().status,
      (pollError) => set({ pollError }),
    ),

  pollFresh: async () => pollFreshBirthStatus(() => get().poll()),

  bootstrapSession: async ({ appSurfaceReason, targetTrades }) => {
    set({ targetTrades });

    let status = get().status ?? (await get().poll());
    if (!status) {
      return false;
    }

    if (get().genesisPinned) {
      set({ uiPhase: "idle", birthSurface: "genesis", pollError: null });
      return false;
    }

    if (isBirthEngineActive(status) || isBirthComplete(status)) {
      if (isBirthEngineActive(status)) {
        set({ uiPhase: "running", birthSurface: "running", pollError: null });
      }
      return true;
    }

    if (!shouldAutoResumeBirth(status, appSurfaceReason)) {
      if (isBirthInterrupted(status) || String(status.status ?? "").toLowerCase() === "idle") {
        set({ birthSurface: "genesis", uiPhase: "idle" });
      }
      return false;
    }

    get().beginBirthRun();
    try {
      await startBirthSessionContinue(targetTrades);
      await get().poll();
      return true;
    } catch (err) {
      set({
        uiPhase: isBirthInterrupted(status) ? "idle" : "error",
        pollError: err instanceof Error ? err.message : "Birth resume failed",
      });
      return false;
    }
  },

  retryBirth: async (options) => {
    set({
      uiPhase: "running",
      birthSurface: "running",
      genesisPinned: false,
      runPinned: true,
      pollError: null,
    });
    try {
      const response = await retryBirthSession(get().targetTrades, options);
      if (!isBirthStartSuccessful(response.status, response)) {
        const message = response.message ?? `Birth retry failed (${response.status})`;
        get().applyStatus(response);
        set({
          uiPhase: recoveryFailureUiPhase(response),
          pollError: message,
        });
        return false;
      }
      get().applyStatus(response);
      await get().poll();
      return true;
    } catch (err) {
      set({
        uiPhase: recoveryFailureUiPhase(get().status),
        pollError: err instanceof Error ? err.message : "Birth restart failed",
      });
      return false;
    }
  },

  acceptChampion: async () => {
    set({
      uiPhase: "running",
      birthSurface: "running",
      genesisPinned: false,
      runPinned: true,
      pollError: null,
    });
    try {
      const response = await acceptChampionSession(get().targetTrades);
      if (!isBirthStartSuccessful(response.status, response)) {
        const message = response.message ?? `Accept champion failed (${response.status})`;
        get().applyStatus(response);
        set({ uiPhase: recoveryFailureUiPhase(response), pollError: message });
        return false;
      }
      get().applyStatus(response);
      await get().poll();
      return true;
    } catch (err) {
      set({
        uiPhase: recoveryFailureUiPhase(get().status),
        pollError: err instanceof Error ? err.message : "Accept champion failed",
      });
      return false;
    }
  },

  resumeBirth: async () => {
    set({
      uiPhase: "running",
      birthSurface: "running",
      genesisPinned: false,
      runPinned: true,
      pollError: null,
    });
    try {
      const response = await resumeBirthSession(get().targetTrades);
      if (!isBirthStartSuccessful(response.status, response)) {
        const message = response.message ?? `Birth resume failed (${response.status})`;
        get().applyStatus(response);
        set({ uiPhase: recoveryFailureUiPhase(response), pollError: message });
        return false;
      }
      get().applyStatus(response);
      await get().poll();
      return true;
    } catch (err) {
      set({
        uiPhase: recoveryFailureUiPhase(get().status),
        pollError: err instanceof Error ? err.message : "Birth resume failed",
      });
      return false;
    }
  },

  resumeStalledStage: async () => {
    set({
      uiPhase: "running",
      birthSurface: "running",
      genesisPinned: false,
      runPinned: true,
      pollError: null,
    });
    try {
      const response = await resumeStalledStageSession(get().targetTrades);
      if (!isBirthStartSuccessful(response.status, response)) {
        const message = response.message ?? `Stage resume failed (${response.status})`;
        get().applyStatus(response);
        set({ uiPhase: "stage_stalled", pollError: message });
        return false;
      }
      get().applyStatus(response);
      await get().poll();
      return true;
    } catch (err) {
      set({
        uiPhase: "stage_stalled",
        pollError: err instanceof Error ? err.message : "Stage resume failed",
      });
      return false;
    }
  },

  executeRecommendedRecovery: async () => {
    set({
      uiPhase: "running",
      birthSurface: "running",
      genesisPinned: false,
      runPinned: true,
      pollError: null,
    });
    try {
      const response = await autonomousRecoverySession(get().targetTrades);
      if (!isBirthStartSuccessful(response.status, response)) {
        const message = response.message ?? `Autonomous recovery failed (${response.status})`;
        get().applyStatus(response);
        set({ uiPhase: "stage_stalled", pollError: message });
        return false;
      }
      get().applyStatus(response);
      await get().poll();
      return true;
    } catch (err) {
      set({
        uiPhase: "stage_stalled",
        pollError: err instanceof Error ? err.message : "Autonomous recovery failed",
      });
      return false;
    }
  },

  expandAndRetryStalledStage: async () => {
    set({ uiPhase: "running", birthSurface: "running", pollError: null });
    try {
      const response = await expandAndRetryStalledStageSession(get().targetTrades);
      if (!isBirthStartSuccessful(response.status, response)) {
        const message = response.message ?? `Expand and retry failed (${response.status})`;
        get().applyStatus(response);
        set({ uiPhase: "stage_stalled", pollError: message });
        return false;
      }
      get().applyStatus(response);
      await get().poll();
      return true;
    } catch (err) {
      set({
        uiPhase: "stage_stalled",
        pollError: err instanceof Error ? err.message : "Expand and retry failed",
      });
      return false;
    }
  },

  reuseDataBirth: async () => {
    set({ uiPhase: "running", birthSurface: "running", pollError: null });
    try {
      const response = await reuseDataBirthSession(get().targetTrades);
      if (!isBirthStartSuccessful(response.status, response)) {
        const message = response.message ?? `Birth reuse failed (${response.status})`;
        get().applyStatus(response);
        set({ uiPhase: recoveryFailureUiPhase(response), pollError: message });
        return false;
      }
      get().applyStatus(response);
      await get().poll();
      return true;
    } catch (err) {
      set({
        uiPhase: recoveryFailureUiPhase(get().status),
        pollError: err instanceof Error ? err.message : "Birth reuse failed",
      });
      return false;
    }
  },

  stopBirthRun: async () => {
    // Pin Genesis *before* the network call so the operator never waits on
    // PPO teardown for navigation (backend stop is signal + pause SSOT only).
    set({
      pollError: null,
      uiPhase: "idle",
      birthSurface: "genesis",
      genesisPinned: true,
      runPinned: false,
    });
    let stopError: string | null = null;
    try {
      const stopResult = await stopBirthSession();
      const stopStatus = String(stopResult.status ?? "").toLowerCase();
      if (stopStatus === "rejected") {
        throw new Error(String(stopResult.message ?? "Birth stop rejected"));
      }

      // Single fast status refresh — do not poll-wait for engine drain.
      // Resume uses on-disk checkpoint_resumable (visible while stopping).
      let payload: BirthStatusPayload | null = null;
      try {
        payload = await get().pollFresh();
      } catch {
        try {
          payload = await fetchBirthStatusTyped();
        } catch {
          payload = null;
        }
      }

      if (payload) {
        // Prefer server flag; if stop response already says resumable, surface it.
        const stopResumable = stopResult.checkpoint_resumable === true;
        const merged: BirthStatusPayload = stopResumable
          ? { ...payload, checkpoint_resumable: true }
          : payload;
        get().applyStatus(merged);
      } else if (stopResult.checkpoint_resumable === true) {
        const prev = get().status;
        if (prev) {
          get().applyStatus({
            ...prev,
            live: false,
            checkpoint_resumable: true,
            progress: {
              ...(prev.progress ?? {}),
              stage: "paused",
              phase: "paused",
              user_initiated_stop: true,
            },
          });
        }
      }

      set({
        uiPhase: "idle",
        birthSurface: "genesis",
        genesisPinned: true,
        runPinned: false,
        pollError: null,
      });
    } catch (err) {
      stopError = err instanceof Error ? err.message : "Birth stop failed";
      try {
        const payload = await fetchBirthStatusTyped();
        get().applyStatus(payload);
      } catch {
        /* keep last known status */
      }
      set({
        pollError: stopError,
        uiPhase: "idle",
        birthSurface: "genesis",
        genesisPinned: true,
        runPinned: false,
      });
    }

    return stopError == null;
  },

  wipeBirthData: async (options?: { preserveTickCache?: boolean }) => {
    traceBirthWipe("store.wipe.start", { preserveTickCache: Boolean(options?.preserveTickCache) });
    try {
      traceBirthWipe("store.wipe.api_request");
      const startedAt = performance.now();
      const apiResult = await wipeAllBirthData({
        preserveTickCache: Boolean(options?.preserveTickCache),
      });
      traceBirthWipe("store.wipe.api_response", {
        elapsedMs: Math.round(performance.now() - startedAt),
        status: apiResult.status,
        checkpointResumable: apiResult.checkpoint_resumable,
        removedCount: Array.isArray(apiResult.removed_artifacts)
          ? apiResult.removed_artifacts.length
          : undefined,
        message: apiResult.message,
      });

      const apiStatus = String(apiResult.status ?? "").toLowerCase();
      if (apiStatus === "rejected") {
        const error =
          String(apiResult.message ?? "").trim() ||
          "Birth Phase draait nog — stop eerst, wacht enkele seconden, probeer opnieuw.";
        traceBirthWipe("store.wipe.rejected", { error }, "error");
        return { ok: false, error };
      }

      const apiClean = apiStatus === "wiped" && apiResult.checkpoint_resumable !== true;
      let verification: ReturnType<typeof verifyBirthWipeSucceeded> = { ok: false, error: "" };
      let statusPayload: BirthStatusPayload | null = null;
      for (let attempt = 0; attempt < WIPE_VERIFY_ATTEMPTS; attempt += 1) {
        statusPayload = await get().pollFresh();
        verification = verifyBirthWipeSucceeded({
          apiStatus,
          apiCheckpointResumable: apiResult.checkpoint_resumable,
          polledStatus: statusPayload,
        });
        traceBirthWipe("store.wipe.verify_attempt", {
          attempt: attempt + 1,
          maxAttempts: WIPE_VERIFY_ATTEMPTS,
          verifyOk: verification.ok,
          verifyError: "error" in verification ? verification.error : undefined,
          polledStatus: statusPayload?.status,
          polledLive: statusPayload?.live,
          polledCheckpointResumable: statusPayload?.checkpoint_resumable,
        }, verification.ok ? "debug" : "warn");
        if (verification.ok) {
          break;
        }
        if (attempt < WIPE_VERIFY_ATTEMPTS - 1) {
          await new Promise((resolve) => setTimeout(resolve, WIPE_VERIFY_DELAY_MS));
        }
      }

      if (!verification.ok && apiClean) {
        traceBirthWipe(
          "store.wipe.verify_trust_api",
          { apiStatus, apiCheckpointResumable: apiResult.checkpoint_resumable },
          "warn",
        );
        verification = { ok: true };
      }

      if (!verification.ok) {
        const error =
          "error" in verification
            ? verification.error
            : "Wipe voltooid maar status kon niet worden geverifieerd.";
        traceBirthWipe("store.wipe.verify_failed", { error }, "error");
        return { ok: false, error };
      }

      traceBirthWipe("store.wipe.reset_store");
      get().reset();
      if (apiResult.redirect_to_genesis !== false) {
        get().returnToGenesis();
      }
      await get().pollFresh();
      const removedCount = Array.isArray(apiResult.removed_artifacts)
        ? apiResult.removed_artifacts.length
        : undefined;
      const message =
        removedCount === 0
          ? "Geen birth-data gevonden — status is al schoon."
          : String(apiResult.message ?? "").trim() ||
            "All birth data wiped — ready for a clean start.";
      traceBirthWipe("store.wipe.success", { removedCount, message });
      return { ok: true, message, removedCount };
    } catch (e) {
      const error = e instanceof Error ? e.message : "Wipe failed";
      traceBirthWipe("store.wipe.exception", { error }, "error");
      return { ok: false, error };
    }
  },

  beginFinale: () => set({ uiPhase: "finale" }),

  returnToGenesis: () => {
    // Pin first so any applyStatus/poll re-entry honors genesis and stays off error overlays.
    set({
      uiPhase: "idle",
      birthSurface: "genesis",
      genesisPinned: true,
      runPinned: false,
      pollError: null,
    });
    const status = get().status;
    if (status) {
      get().applyStatus(status);
    }
    // Re-assert pin after applyStatus (failed/error payloads previously forced uiPhase back to error).
    set({
      uiPhase: "idle",
      birthSurface: "genesis",
      genesisPinned: true,
      runPinned: false,
      pollError: null,
    });
  },

  reset: () => {
    resetPollCoordinator();
    set({
      status: null,
      milestones: buildMilestones(undefined, "idle"),
      headline: "Organism is being born…",
      uiPhase: "idle",
      birthSurface: "genesis",
      genesisPinned: false,
      runPinned: false,
      pollError: null,
      sessionHydrated: false,
      sessionProbeState: "pending",
    });
  },
}));