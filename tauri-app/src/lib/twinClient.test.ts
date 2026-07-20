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

describe("twinClient helpers", () => {
  it("buildReviewQueueQuery encodes limit and include_labeled", async () => {
    const { buildReviewQueueQuery } = await import("@/lib/twinClient");
    expect(buildReviewQueueQuery(15)).toBe("limit=15&include_labeled=false");
    expect(buildReviewQueueQuery(10, { includeLabeled: true })).toBe(
      "limit=10&include_labeled=true",
    );
  });

  it("isModeReady accepts bool and readiness objects", async () => {
    const { isModeReady } = await import("@/lib/twinClient");
    expect(isModeReady(true)).toBe(true);
    expect(isModeReady(false)).toBe(false);
    expect(isModeReady({ promoted: true, fail_reasons: [] })).toBe(true);
    expect(isModeReady({ promoted: false, fail_reasons: ["agreement"] })).toBe(false);
    expect(isModeReady({ ready: true })).toBe(true);
    expect(isModeReady({ ok: true })).toBe(true);
    expect(isModeReady({ passed: true })).toBe(true);
    expect(isModeReady({ ready: false })).toBe(false);
    expect(isModeReady(null)).toBe(false);
  });

  it("formatTwinPct handles fractions and percents", async () => {
    const { formatTwinPct } = await import("@/lib/twinClient");
    expect(formatTwinPct(0.82)).toBe("82.0%");
    expect(formatTwinPct(82)).toBe("82.0%");
    expect(formatTwinPct(null)).toBe("—");
  });

  it("formatConfidenceDistribution summarizes buckets", async () => {
    const { formatConfidenceDistribution } = await import("@/lib/twinClient");
    expect(formatConfidenceDistribution(null)).toContain("No scored");
    expect(
      formatConfidenceDistribution({
        n: 10,
        lt_50: 1,
        b50_60: 2,
        b60_80: 3,
        gte_80: 4,
      }),
    ).toContain("n=10");
  });

  it("twinScoreOf prefers score then confidence", async () => {
    const { twinScoreOf } = await import("@/lib/twinClient");
    expect(twinScoreOf({ score: 0.9, confidence: 0.1 })).toBe(0.9);
    expect(twinScoreOf({ confidence: 0.55 })).toBe(0.55);
    expect(twinScoreOf({})).toBeNull();
  });
});

describe("twinClient HTTP", () => {
  beforeEach(() => {
    const storage = mockStorage();
    storage.setItem(DEFAULT_LUMINA_API_KEY_LS_KEY, "test-key");
    vi.stubGlobal("window", { localStorage: storage });
    vi.stubGlobal("localStorage", storage);
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.resetModules();
  });

  it("fetchTwinMetrics hits /api/twin/metrics with API key", async () => {
    vi.mocked(fetch).mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        local_only: true,
        twin_steve_agreement_pct: 85,
        confidence_distribution: { n: 5, gte_80: 3 },
        risk_flag_top: { leverage: 2 },
      }),
    } as Response);

    const { fetchTwinMetrics } = await import("@/lib/twinClient");
    const m = await fetchTwinMetrics();
    expect(m.local_only).toBe(true);
    expect(m.twin_steve_agreement_pct).toBe(85);
    expect(fetch).toHaveBeenCalled();
    const [url, init] = vi.mocked(fetch).mock.calls[0] as [string, RequestInit];
    expect(String(url)).toContain("/api/twin/metrics");
    expect((init.headers as Record<string, string>)["X-API-Key"]).toBe("test-key");
  });

  it("fetchTwinReviewQueueFull uses include_labeled query", async () => {
    vi.mocked(fetch).mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        items: [{ dna_hash: "abc", score: 0.9 }],
        count: 1,
        high_stakes_count: 0,
        local_only: true,
      }),
    } as Response);

    const { fetchTwinReviewQueueFull } = await import("@/lib/twinClient");
    const q = await fetchTwinReviewQueueFull(12, { includeLabeled: true });
    expect(q.items).toHaveLength(1);
    expect(q.count).toBe(1);
    const [url] = vi.mocked(fetch).mock.calls[0] as [string];
    expect(String(url)).toContain("include_labeled=true");
    expect(String(url)).toContain("limit=12");
  });

  it("postTwinPromote posts target body", async () => {
    vi.mocked(fetch).mockResolvedValueOnce({
      ok: true,
      json: async () => ({ promoted: true, mode: "assisted" }),
    } as Response);

    const { postTwinPromote } = await import("@/lib/twinClient");
    const res = await postTwinPromote("assisted");
    expect(res.promoted).toBe(true);
    const [, init] = vi.mocked(fetch).mock.calls[0] as [string, RequestInit];
    expect(init.method).toBe("POST");
    expect(JSON.parse(String(init.body))).toEqual({ target: "assisted" });
  });

  it("throws readable error when API key missing", async () => {
    localStorage.removeItem(DEFAULT_LUMINA_API_KEY_LS_KEY);
    const { fetchTwinMetrics } = await import("@/lib/twinClient");
    await expect(fetchTwinMetrics()).rejects.toThrow(/API key/i);
  });
});
