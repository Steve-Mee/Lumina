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
  isBirthFailed,
  isBirthInterrupted,
  isBirthRunning,
  isBirthStageStalled,
  resolveBirthHeadline,
  type BirthMilestone,
} from "@/lib/birthPhaseModel";
import { shouldAutoResumeBirth } from "@/lib/birthRecoveryModel";

export type BirthUiPhase =
  | "idle"
  | "running"
  | "finale"
  | "error"
  | "certificate_failed"
  | "stage_stalled";

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
  pollError: string | null;
  targetTrades: number;
  setTargetTrades: (n: number) => void;
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
  beginFinale: () => void;
  reset: () => void;
}

export const useBirthStore = create<BirthState>((set, get) => ({
  status: null,
  milestones: buildMilestones(undefined, "idle"),
  headline: "Organism is being born…",
  uiPhase: "idle",
  pollError: null,
  targetTrades: 25000,

  setTargetTrades: (n) => set({ targetTrades: n }),

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
      uiPhase = "certificate_failed";
    } else if (isBirthComplete(payload)) {
      uiPhase = "finale";
    } else if (isBirthStageStalled(payload)) {
      uiPhase = "stage_stalled";
    } else if (isBirthRunning(payload)) {
      uiPhase = "running";
    } else if (isBirthFailed(payload)) {
      uiPhase = "error";
    } else if (isBirthInterrupted(payload)) {
      uiPhase = "idle";
    }

    set({
      status: payload,
      milestones,
      headline,
      uiPhase,
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

    if (isBirthRunning(status) || isBirthComplete(status)) {
      return true;
    }

    if (!shouldAutoResumeBirth(status, appSurfaceReason)) {
      return false;
    }

    set({ uiPhase: "running", pollError: null });
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
    set({ uiPhase: "running", pollError: null });
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
    set({ uiPhase: "running", pollError: null });
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
    set({ uiPhase: "running", pollError: null });
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
    set({ uiPhase: "running", pollError: null });
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
    set({ uiPhase: "running", pollError: null });
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

  beginFinale: () => set({ uiPhase: "finale" }),

  reset: () =>
    set({
      status: null,
      milestones: buildMilestones(undefined, "idle"),
      headline: "Organism is being born…",
      uiPhase: "idle",
      pollError: null,
    }),
}));
