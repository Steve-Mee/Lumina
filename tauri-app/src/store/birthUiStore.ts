import { create } from "zustand";

import type { BirthWipeResult } from "@/lib/birthClient";
import { traceBirthWipe } from "@/lib/birthWipeTrace";

const DISMISS_GUARD_MS = 400;

export type WipeConfirmStep = 0 | 1 | 2;

/** reset = checkpoint/PPO weg, tick cache blijft; full = alles incl. tick cache */
export type WipeConfirmKind = "reset" | "full";

interface BirthUiState {
  /** When true, recovery actions and deck entry run without operator clicks. */
  autonomousMode: boolean;
  dismissGuardUntil: number;
  wipeConfirmStep: WipeConfirmStep;
  wipeConfirmKind: WipeConfirmKind;
  wipeConfirmWiping: boolean;
  wipeConfirmError: string | null;
  wipeSuccess: BirthWipeResult | null;
  stopConfirmOpen: boolean;
  stopConfirmStopping: boolean;
  armDismissGuard: () => void;
  shouldBlockDismiss: () => boolean;
  openWipeConfirm: (kind?: WipeConfirmKind) => void;
  setWipeConfirmStep: (step: WipeConfirmStep) => void;
  closeWipeConfirm: () => void;
  setWipeConfirmWiping: (wiping: boolean) => void;
  setWipeConfirmError: (error: string | null) => void;
  setWipeSuccess: (result: BirthWipeResult | null) => void;
  openStopConfirm: () => void;
  closeStopConfirm: () => void;
  setStopConfirmStopping: (stopping: boolean) => void;
  resetBirthUi: () => void;
}

const initialBirthUiState = {
  autonomousMode: true,
  dismissGuardUntil: 0,
  wipeConfirmStep: 0 as WipeConfirmStep,
  wipeConfirmKind: "reset" as WipeConfirmKind,
  wipeConfirmWiping: false,
  wipeConfirmError: null as string | null,
  wipeSuccess: null as BirthWipeResult | null,
  stopConfirmOpen: false,
  stopConfirmStopping: false,
};

export const useBirthUiStore = create<BirthUiState>((set, get) => ({
  ...initialBirthUiState,

  armDismissGuard: () => {
    set({ dismissGuardUntil: Date.now() + DISMISS_GUARD_MS });
  },

  shouldBlockDismiss: () => Date.now() < get().dismissGuardUntil,

  openWipeConfirm: (kind: WipeConfirmKind = "reset") => {
    get().armDismissGuard();
    set({
      wipeConfirmStep: 1,
      wipeConfirmKind: kind,
      wipeConfirmError: null,
    });
    traceBirthWipe("ui.wipe_dialog.open", { step: 1, kind, source: "birthUiStore" });
  },

  setWipeConfirmStep: (step) => set({ wipeConfirmStep: step }),

  closeWipeConfirm: () => {
    // Always allow dismiss — if a wipe is mid-flight, clear wiping flag so the
    // dialog cannot soft-lock after a hung request.
    set({
      wipeConfirmStep: 0,
      wipeConfirmError: null,
      wipeConfirmKind: "reset",
      wipeConfirmWiping: false,
    });
  },

  setWipeConfirmWiping: (wiping) => set({ wipeConfirmWiping: wiping }),

  setWipeConfirmError: (error) => set({ wipeConfirmError: error }),

  setWipeSuccess: (result) => set({ wipeSuccess: result }),

  openStopConfirm: () => {
    get().armDismissGuard();
    set({ stopConfirmOpen: true });
    traceBirthWipe("ui.stop_dialog.open", { source: "birthUiStore" });
  },

  closeStopConfirm: () => set({ stopConfirmOpen: false }),

  setStopConfirmStopping: (stopping) => set({ stopConfirmStopping: stopping }),

  resetBirthUi: () => set({ ...initialBirthUiState }),
}));
