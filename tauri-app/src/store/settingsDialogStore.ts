import { create } from "zustand";

export type SettingsTab = "apiKey" | "bot" | "visual";

interface SettingsDialogState {
  open: boolean;
  tab: SettingsTab;
  openSettings: (tab?: SettingsTab) => void;
  closeSettings: () => void;
  setTab: (tab: SettingsTab) => void;
}

export const useSettingsDialogStore = create<SettingsDialogState>((set) => ({
  open: false,
  tab: "apiKey",
  openSettings: (tab = "apiKey") => set({ open: true, tab }),
  closeSettings: () => set({ open: false }),
  setTab: (tab) => set({ tab }),
}));
