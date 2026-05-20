import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { DEFAULT_LUMINA_API_KEY_LS_KEY } from "@/lib/monitoringClient";

function mockStorage(): Storage {
  const map = new Map<string, string>();
  return {
    get length() {
      return map.size;
    },
    clear: () => map.clear(),
    getItem: (key: string) => map.get(key) ?? null,
    setItem: (key: string, value: string) => map.set(key, value),
    removeItem: (key: string) => map.delete(key),
    key: (index: number) => [...map.keys()][index] ?? null,
  } as Storage;
}

describe("fetchAndHydrateDeckApiKey", () => {
  beforeEach(() => {
    const storage = mockStorage();
    vi.stubGlobal("window", { localStorage: storage });
    vi.stubGlobal("localStorage", storage);
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.resetModules();
  });

  it("returns true when localStorage already has a key", async () => {
    localStorage.setItem(DEFAULT_LUMINA_API_KEY_LS_KEY, "sk_existing");
    const { fetchAndHydrateDeckApiKey } = await import("@/lib/setupClient");
    const ok = await fetchAndHydrateDeckApiKey();
    expect(ok).toBe(true);
    expect(fetch).not.toHaveBeenCalled();
  });

  it("hydrates from backend when localStorage is empty", async () => {
    vi.mocked(fetch).mockResolvedValueOnce({
      ok: true,
      json: async () => ({ configured: true, api_key: "sk_from_env" }),
    } as Response);

    const { fetchAndHydrateDeckApiKey } = await import("@/lib/setupClient");
    const ok = await fetchAndHydrateDeckApiKey();
    expect(ok).toBe(true);
    expect(localStorage.getItem(DEFAULT_LUMINA_API_KEY_LS_KEY)).toBe("sk_from_env");
  });
});
