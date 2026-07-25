import { create } from "zustand";

import { DEFAULT_LUMINA_API_KEY_LS_KEY } from "@/lib/apiKeyConstants";

interface ApiKeyState {
  configured: boolean;
  hydrate: () => void;
  syncFromStorage: () => void;
  setKey: (key: string) => void;
}

function readConfigured(): boolean {
  if (typeof window === "undefined") return false;
  try {
    return Boolean(localStorage.getItem(DEFAULT_LUMINA_API_KEY_LS_KEY)?.trim());
  } catch {
    return false;
  }
}

export const useApiKeyStore = create<ApiKeyState>((set) => ({
  configured: readConfigured(),
  hydrate: () => set({ configured: readConfigured() }),
  syncFromStorage: () => set({ configured: readConfigured() }),
  setKey: (key) => {
    if (typeof window !== "undefined" && key.trim()) {
      try {
        localStorage.setItem(DEFAULT_LUMINA_API_KEY_LS_KEY, key.trim());
      } catch {
        // ignore storage failures
      }
    }
    set({ configured: readConfigured() });
  },
}));

export const selectApiKeyConfigured = (state: ApiKeyState) => state.configured;
