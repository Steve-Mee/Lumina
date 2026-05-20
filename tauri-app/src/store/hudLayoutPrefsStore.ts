import { create } from "zustand";

import {
  HUD_SHOW_PNL_PREF_KEY,
  readHudLayoutPrefs,
  writeHudLayoutPrefs,
  type HudLayoutPrefs,
} from "@/lib/hudSignalLayout";

interface HudLayoutPrefsState {
  prefs: HudLayoutPrefs;
  hydrate: () => void;
  setPrefs: (next: HudLayoutPrefs) => void;
  toggleShowPnlInSim: () => void;
}

export const useHudLayoutPrefsStore = create<HudLayoutPrefsState>((set, get) => ({
  prefs: readHudLayoutPrefs(),
  hydrate: () => set({ prefs: readHudLayoutPrefs() }),
  setPrefs: (next) => {
    writeHudLayoutPrefs(next);
    set({ prefs: next });
    window.dispatchEvent(new CustomEvent("lumina:hud-prefs"));
  },
  toggleShowPnlInSim: () => {
    const next = { showPnlInSim: !get().prefs.showPnlInSim };
    writeHudLayoutPrefs(next);
    set({ prefs: next });
    window.dispatchEvent(new CustomEvent("lumina:hud-prefs"));
  },
}));

const HUD_PREFS_EVENT = "lumina:hud-prefs";

export function subscribeHudLayoutPrefs(listener: () => void): () => void {
  const onStorage = (event: StorageEvent) => {
    if (event.key === HUD_SHOW_PNL_PREF_KEY) {
      listener();
    }
  };
  const onCustom = () => listener();
  window.addEventListener("storage", onStorage);
  window.addEventListener(HUD_PREFS_EVENT, onCustom);
  return () => {
    window.removeEventListener("storage", onStorage);
    window.removeEventListener(HUD_PREFS_EVENT, onCustom);
  };
}
