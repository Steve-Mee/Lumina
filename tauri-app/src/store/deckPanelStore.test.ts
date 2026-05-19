import { beforeEach, describe, expect, it, vi } from "vitest";

import { useDeckPanelStore } from "@/store/deckPanelStore";

const memoryStorage = new Map<string, string>();

const sessionStorageMock = {
  getItem: (key: string) => memoryStorage.get(key) ?? null,
  setItem: (key: string, value: string) => {
    memoryStorage.set(key, value);
  },
  removeItem: (key: string) => {
    memoryStorage.delete(key);
  },
  clear: () => {
    memoryStorage.clear();
  },
};

vi.stubGlobal("window", { sessionStorage: sessionStorageMock });

describe("deckPanelStore", () => {
  beforeEach(() => {
    memoryStorage.clear();
    useDeckPanelStore.setState({ activeCenterTab: "evolution", activeRightTab: "brief" });
  });

  it("defaults to evolution and brief tabs", () => {
    expect(useDeckPanelStore.getState().activeCenterTab).toBe("evolution");
    expect(useDeckPanelStore.getState().activeRightTab).toBe("brief");
  });

  it("persists active center tab in sessionStorage", () => {
    useDeckPanelStore.getState().setActiveCenterTab("ppo");
    expect(window.sessionStorage.getItem("lumina.deck.centerTab")).toBe("ppo");
  });

  it("persists active right tab in sessionStorage", () => {
    useDeckPanelStore.getState().setActiveRightTab("adaptive");
    expect(window.sessionStorage.getItem("lumina.deck.rightTab")).toBe("adaptive");
  });

  it("hydrates right tab from sessionStorage", () => {
    window.sessionStorage.setItem("lumina.deck.rightTab", "monitor");
    useDeckPanelStore.getState().hydrateRightTab();
    expect(useDeckPanelStore.getState().activeRightTab).toBe("monitor");
  });
});
