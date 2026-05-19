import { create } from "zustand";

export type CenterDeckTab = "evolution" | "ppo" | "readiness";
export type RightDeckTab =
  | "brief"
  | "adaptive"
  | "performance"
  | "realOps"
  | "evolutionApprovals"
  | "liveActivity"
  | "monitor"
  | "community"
  | "hardware"
  | "admin";

const CENTER_TAB_STORAGE_KEY = "lumina.deck.centerTab";
const RIGHT_TAB_STORAGE_KEY = "lumina.deck.rightTab";

const RIGHT_TABS: RightDeckTab[] = [
  "brief",
  "adaptive",
  "performance",
  "realOps",
  "evolutionApprovals",
  "liveActivity",
  "monitor",
  "community",
  "hardware",
  "admin",
];

interface DeckPanelStore {
  activeCenterTab: CenterDeckTab;
  activeRightTab: RightDeckTab;
  setActiveCenterTab: (tab: CenterDeckTab) => void;
  setActiveRightTab: (tab: RightDeckTab) => void;
  hydrateCenterTab: () => void;
  hydrateRightTab: () => void;
}

function readStoredCenterTab(): CenterDeckTab {
  if (typeof window === "undefined") return "evolution";
  const stored = window.sessionStorage.getItem(CENTER_TAB_STORAGE_KEY);
  if (stored === "ppo" || stored === "readiness") return stored;
  return "evolution";
}

function readStoredRightTab(): RightDeckTab {
  if (typeof window === "undefined") return "brief";
  const stored = window.sessionStorage.getItem(RIGHT_TAB_STORAGE_KEY);
  if (stored && RIGHT_TABS.includes(stored as RightDeckTab)) return stored as RightDeckTab;
  return "brief";
}

export const useDeckPanelStore = create<DeckPanelStore>((set) => ({
  activeCenterTab: "evolution",
  activeRightTab: "brief",
  setActiveCenterTab: (tab) => {
    if (typeof window !== "undefined") {
      window.sessionStorage.setItem(CENTER_TAB_STORAGE_KEY, tab);
    }
    set({ activeCenterTab: tab });
  },
  setActiveRightTab: (tab) => {
    if (typeof window !== "undefined") {
      window.sessionStorage.setItem(RIGHT_TAB_STORAGE_KEY, tab);
    }
    set({ activeRightTab: tab });
  },
  hydrateCenterTab: () => {
    set({ activeCenterTab: readStoredCenterTab() });
  },
  hydrateRightTab: () => {
    set({ activeRightTab: readStoredRightTab() });
  },
}));

export const selectActiveCenterTab = (state: DeckPanelStore) => state.activeCenterTab;
export const selectActiveRightTab = (state: DeckPanelStore) => state.activeRightTab;
