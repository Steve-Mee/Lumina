import { create } from "zustand";

import {
  resolveRenderConfig,
  type RenderConfig,
  type VisualQuality,
} from "@/lib/visualQualityPresets";

const VISUAL_QUALITY_STORAGE_KEY = "lumina.visualQuality";

const VALID_QUALITIES: VisualQuality[] = ["low", "balanced", "high"];

interface VisualSettingsState {
  visualQuality: VisualQuality;
}

interface VisualSettingsActions {
  setVisualQuality: (quality: VisualQuality) => void;
  hydrateVisualSettings: () => void;
}

export type VisualSettingsStore = VisualSettingsState & VisualSettingsActions;

function readStoredQuality(): VisualQuality | null {
  if (typeof window === "undefined") {
    return null;
  }
  try {
    const stored = window.localStorage.getItem(VISUAL_QUALITY_STORAGE_KEY);
    if (stored && VALID_QUALITIES.includes(stored as VisualQuality)) {
      return stored as VisualQuality;
    }
  } catch {
    return null;
  }
  return null;
}

function persistQuality(quality: VisualQuality): void {
  if (typeof window === "undefined") {
    return;
  }
  try {
    window.localStorage.setItem(VISUAL_QUALITY_STORAGE_KEY, quality);
  } catch {
    // ignore storage failures
  }
}

export const useVisualSettingsStore = create<VisualSettingsStore>((set) => ({
  visualQuality: "balanced",
  setVisualQuality: (quality) => {
    persistQuality(quality);
    set({ visualQuality: quality });
  },
  hydrateVisualSettings: () => {
    const stored = readStoredQuality();
    if (stored) {
      set({ visualQuality: stored });
    }
  },
}));

export const selectVisualQuality = (state: VisualSettingsStore) =>
  state.visualQuality;

export const selectRenderConfig = (state: VisualSettingsStore): RenderConfig =>
  resolveRenderConfig(state.visualQuality);
