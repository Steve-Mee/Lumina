import { create } from "zustand";

const STORAGE_KEY = "lumina_panel_refresh_seconds";

export type PanelRefreshSeconds = 5 | 10 | 15 | 30 | 60;

function readStored(): PanelRefreshSeconds {
  try {
    const raw = Number(localStorage.getItem(STORAGE_KEY));
    if (raw === 5 || raw === 10 || raw === 15 || raw === 30 || raw === 60) {
      return raw;
    }
  } catch {
    /* ignore */
  }
  return 10;
}

interface PanelRefreshState {
  seconds: PanelRefreshSeconds;
  hydrate: () => void;
  setSeconds: (value: PanelRefreshSeconds) => void;
}

export const usePanelRefreshStore = create<PanelRefreshState>((set) => ({
  seconds: readStored(),
  hydrate: () => set({ seconds: readStored() }),
  setSeconds: (value) => {
    try {
      localStorage.setItem(STORAGE_KEY, String(value));
    } catch {
      /* ignore */
    }
    set({ seconds: value });
  },
}));

export function selectPanelRefreshMs(state: PanelRefreshState): number {
  return state.seconds * 1000;
}
