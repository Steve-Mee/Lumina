import { create } from "zustand";

import type { BirthStatusPayload } from "@/lib/birthClient";
import {
  fetchBirthStatusTyped,
  isBirthStartSuccessful,
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

export type BirthUiPhase = "idle" | "running" | "finale" | "error" | "certificate_failed";

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
      uiPhase = "idle";
    } else if (isBirthFailed(payload)) {
      uiPhase = "error";
    } else if (isBirthInterrupted(payload)) {
      uiPhase = "idle";
    } else if (isBirthRunning(payload)) {
      uiPhase = "running";
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
      if (!isBirthStartSuccessful(response.status)) {
        const message = response.message ?? `Birth retry failed (${response.status})`;
        get().applyStatus(response);
        set({
          uiPhase: "certificate_failed",
          pollError: message,
        });
        return false;
      }
      get().applyStatus(response);
      await get().poll();
      return true;
    } catch (err) {
      set({
        uiPhase: "certificate_failed",
        pollError: err instanceof Error ? err.message : "Birth restart failed",
      });
      return false;
    }
  },

  resumeBirth: async () => {
    set({ uiPhase: "running", pollError: null });
    try {
      const response = await resumeBirthSession(get().targetTrades);
      if (!isBirthStartSuccessful(response.status)) {
        const message = response.message ?? `Birth resume failed (${response.status})`;
        get().applyStatus(response);
        set({ uiPhase: "certificate_failed", pollError: message });
        return false;
      }
      get().applyStatus(response);
      await get().poll();
      return true;
    } catch (err) {
      set({
        uiPhase: "certificate_failed",
        pollError: err instanceof Error ? err.message : "Birth resume failed",
      });
      return false;
    }
  },

  reuseDataBirth: async () => {
    set({ uiPhase: "running", pollError: null });
    try {
      const response = await reuseDataBirthSession(get().targetTrades);
      if (!isBirthStartSuccessful(response.status)) {
        const message = response.message ?? `Birth reuse failed (${response.status})`;
        get().applyStatus(response);
        set({ uiPhase: "certificate_failed", pollError: message });
        return false;
      }
      get().applyStatus(response);
      await get().poll();
      return true;
    } catch (err) {
      set({
        uiPhase: "certificate_failed",
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
