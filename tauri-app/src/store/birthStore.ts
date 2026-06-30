import { create } from "zustand";

import type { BirthStatusPayload } from "@/lib/birthClient";
import {
  expandAndRetryStalledStageSession,
  fetchBirthStatusTyped,
  isBirthStartSuccessful,
  resumeStalledStageSession,
  retryBirthSession,
  resumeBirthSession,
  reuseDataBirthSession,
  startBirthSessionContinue,
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
import { shouldAutoResumeBirth } from "@/lib/birthRecoveryModel";
import { stopBirth } from "@/lib/runtimeClient";

export type BirthUiPhase =
  | "idle"
  | "running"
  | "finale"
  | "error"
  | "certificate_failed"
  | "stage_stalled";

export type BirthSurface = "genesis" | "running" | "recovery";

function resolveBirthSurface(
  uiPhase: BirthUiPhase,
  current: BirthSurface,
  payload: BirthStatusPayload,
  genesisPinned: boolean,
): BirthSurface {
  if (uiPhase === "certificate_failed" || uiPhase === "stage_stalled" || uiPhase === "error") {
    return "recovery";
  }
  if (uiPhase === "finale") {
    return "running";
  }
  if (genesisPinned || (uiPhase === "idle" && isBirthInterrupted(payload))) {
    return "genesis";
  }
  if (uiPhase === "running" || isBirthEngineActive(payload)) {
    return "running";
  }
  if (uiPhase === "idle") {
    return "genesis";
  }
  if (current === "recovery" && uiPhase === "idle") {
    return "genesis";
  }
  return current;
}

function recoveryFailureUiPhase(status: BirthStatusPayload | null): BirthUiPhase {
  if (status == null) {
    return "error";
  }
  if (isBirthStageStalled(status)) {
    return "stage_stalled";
  }
  if (isBirthCertificateFailed(status)) {
    return "certificate_failed";
  }
  return "error";
}

interface BirthState {
  status: BirthStatusPayload | null;
  milestones: BirthMilestone[];
  headline: string;
  uiPhase: BirthUiPhase;
  birthSurface: BirthSurface;
  genesisPinned: boolean;
  pollError: string | null;
  targetTrades: number;
  setTargetTrades: (n: number) => void;
  setBirthSurface: (surface: BirthSurface) => void;
  beginBirthRun: () => void;
  applyStatus: (payload: BirthStatusPayload) => void;
  poll: () => Promise<BirthStatusPayload | null>;
  bootstrapSession: (context: {
    appSurfaceReason?: string;
    targetTrades: number;
  }) => Promise<boolean>;
  retryBirth: (options?: { wipe?: boolean }) => Promise<boolean>;
  resumeBirth: () => Promise<boolean>;
  resumeStalledStage: () => Promise<boolean>;
  expandAndRetryStalledStage: () => Promise<boolean>;
  reuseDataBirth: () => Promise<boolean>;
  stopBirthRun: () => Promise<boolean>;
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
  pollError: null,
  targetTrades: 25000,

  setTargetTrades: (n) => set({ targetTrades: n }),

  setBirthSurface: (surface) => set({ birthSurface: surface }),

  beginBirthRun: () =>
    set({
      uiPhase: "running",
      birthSurface: "running",
      genesisPinned: false,
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

    if (get().uiPhase === "finale") {
      /* keep finale until parent transitions */
    } else if (isBirthCertificateFailed(payload)) {
      uiPhase = get().genesisPinned ? "idle" : "certificate_failed";
    } else if (isBirthComplete(payload)) {
      uiPhase = "finale";
    } else if (isBirthStageStalled(payload)) {
      uiPhase = "stage_stalled";
    } else if (isBirthEngineActive(payload)) {
      uiPhase = get().genesisPinned ? "idle" : "running";
    } else if (isBirthFailed(payload)) {
      uiPhase = "error";
    } else if (isBirthInterrupted(payload)) {
      uiPhase = "idle";
    } else if (get().genesisPinned) {
      uiPhase = "idle";
    }

    const birthSurface = resolveBirthSurface(uiPhase, get().birthSurface, payload, get().genesisPinned);

    set({
      status: payload,
      milestones,
      headline,
      uiPhase,
      birthSurface,
      pollError: null,
    });
  },

  poll: async () => {
    try {
      const payload = await fetchBirthStatusTyped();
      get().applyStatus(payload);
      return payload;
    } catch (err) {
      set({
        pollError: err instanceof Error ? err.message : "Failed to poll birth status",
      });
      return null;
    }
  },

  bootstrapSession: async ({ appSurfaceReason, targetTrades }) => {
    set({ targetTrades });

    let status = get().status ?? (await get().poll());
    if (!status) {
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
    set({ uiPhase: "running", birthSurface: "running", pollError: null });
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

  resumeBirth: async () => {
    set({ uiPhase: "running", birthSurface: "running", pollError: null });
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
    set({ uiPhase: "running", birthSurface: "running", pollError: null });
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
    set({ uiPhase: "idle", birthSurface: "genesis", genesisPinned: true, pollError: null });
    try {
      await stopBirth();
      const payload = await fetchBirthStatusTyped();
      get().applyStatus(payload);
      set({ uiPhase: "idle", birthSurface: "genesis", genesisPinned: true, pollError: null });
      return true;
    } catch (err) {
      set({
        pollError: err instanceof Error ? err.message : "Birth stop failed",
      });
      return false;
    }
  },

  beginFinale: () => set({ uiPhase: "finale" }),

  returnToGenesis: () => {
    set({ uiPhase: "idle", birthSurface: "genesis", genesisPinned: true, pollError: null });
    const status = get().status;
    if (status) {
      get().applyStatus(status);
      set({ uiPhase: "idle", birthSurface: "genesis", genesisPinned: true, pollError: null });
    }
  },

  reset: () =>
    set({
      status: null,
      milestones: buildMilestones(undefined, "idle"),
      headline: "Organism is being born…",
      uiPhase: "idle",
      birthSurface: "genesis",
      genesisPinned: false,
      pollError: null,
    }),
}));
