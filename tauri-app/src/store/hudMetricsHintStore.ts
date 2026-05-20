import { create } from "zustand";

import type { HudContextualKind } from "@/lib/hudSignalLayout";

interface HudMetricsHintState {
  active: boolean;
  kind: Exclude<HudContextualKind, "none"> | null;
  pulse: boolean;
  setAnnexHint: (active: boolean, kind: Exclude<HudContextualKind, "none"> | null) => void;
  pulseHint: () => void;
  clearPulse: () => void;
}

export const useHudMetricsHintStore = create<HudMetricsHintState>((set) => ({
  active: false,
  kind: null,
  pulse: false,
  setAnnexHint: (active, kind) => set({ active, kind, pulse: false }),
  pulseHint: () => set({ pulse: true }),
  clearPulse: () => set({ pulse: false }),
}));

export const selectHudMetricsHintActive = (state: HudMetricsHintState) => state.active;
export const selectHudMetricsHintPulse = (state: HudMetricsHintState) => state.pulse;
