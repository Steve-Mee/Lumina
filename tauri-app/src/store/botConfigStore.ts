import { create } from "zustand";

import {
  botConfigDraftEquals,
  defaultBotConfigDraft,
  hydrateBotConfigDraftFromPayload,
  hydrateBotConfigFromDefaults,
  toBotConfigPayload,
  type BotConfigDraft,
} from "@/lib/botConfigDraft";
import { fetchOnboardingStatus, postBotConfig } from "@/lib/setupClient";

interface BotConfigState {
  draft: BotConfigDraft;
  baseline: BotConfigDraft;
  loading: boolean;
  saving: boolean;
  error: string | null;
  loadFromBackend: () => Promise<void>;
  updateDraft: (patch: Partial<BotConfigDraft>) => void;
  save: () => Promise<boolean>;
  isDirty: () => boolean;
  resetDraft: () => void;
}

export const useBotConfigStore = create<BotConfigState>((set, get) => ({
  draft: defaultBotConfigDraft(),
  baseline: defaultBotConfigDraft(),
  loading: false,
  saving: false,
  error: null,

  loadFromBackend: async () => {
    set({ loading: true, error: null });
    try {
      const payload = await fetchOnboardingStatus();
      const draft = hydrateBotConfigDraftFromPayload(payload);
      set({ draft, baseline: draft, loading: false });
    } catch (err) {
      set({
        loading: false,
        error: err instanceof Error ? err.message : "Failed to load bot configuration",
      });
    }
  },

  updateDraft: (patch) =>
    set((state) => ({
      draft: {
        ...state.draft,
        ...patch,
        risk: { ...state.draft.risk, ...(patch.risk ?? {}) },
        evolution: { ...state.draft.evolution, ...(patch.evolution ?? {}) },
        preferences: { ...state.draft.preferences, ...(patch.preferences ?? {}) },
      },
    })),

  save: async () => {
    set({ saving: true, error: null });
    try {
      const { draft } = get();
      const result = await postBotConfig(toBotConfigPayload(draft));
      if (!result.success) {
        set({ saving: false, error: "Save failed" });
        return false;
      }
      const refreshed = hydrateBotConfigFromDefaults(result.defaults);
      set({ draft: refreshed, baseline: refreshed, saving: false });
      return true;
    } catch (err) {
      set({
        saving: false,
        error: err instanceof Error ? err.message : "Failed to save bot configuration",
      });
      return false;
    }
  },

  isDirty: () => !botConfigDraftEquals(get().draft, get().baseline),

  resetDraft: () => set((state) => ({ draft: state.baseline, error: null })),
}));
