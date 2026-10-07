import { create } from "zustand";

import { fetchNtAccounts, saveNtAccounts, type NtAccountsResponse } from "@/lib/setupClient";

type NtAccountGateState = {
  loaded: boolean;
  failed: boolean;
  pairComplete: boolean;
  error: string;
  snapshot: NtAccountsResponse | null;
  refresh: () => Promise<void>;
  save: (demo: string, real: string) => Promise<NtAccountsResponse>;
};

export const useNtAccountGateStore = create<NtAccountGateState>((set) => ({
  loaded: false,
  failed: false,
  pairComplete: false,
  error: "",
  snapshot: null,
  refresh: async () => {
    try {
      const snapshot = await fetchNtAccounts();
      set({
        loaded: true,
        failed: false,
        pairComplete: Boolean(snapshot.pair_complete),
        error: snapshot.pair_error || "",
        snapshot,
      });
    } catch (err) {
      set({
        loaded: true,
        failed: true,
        pairComplete: false,
        error: err instanceof Error ? err.message : "De rekeningen zijn niet gelezen.",
        snapshot: null,
      });
    }
  },
  save: async (demo, real) => {
    const snapshot = await saveNtAccounts(demo, real);
    set({
      loaded: true,
      failed: false,
      pairComplete: Boolean(snapshot.pair_complete),
      error: snapshot.pair_error || "",
      snapshot,
    });
    return snapshot;
  },
}));
