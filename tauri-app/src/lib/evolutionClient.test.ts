import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  approveProposal,
  fetchEvolutionProposals,
  rejectProposal,
  resolveDefaultChallengerName,
} from "@/lib/evolutionClient";

const memoryStorage = new Map<string, string>();

describe("evolutionClient", () => {
  beforeEach(() => {
    memoryStorage.clear();
    memoryStorage.set("lumina_api_key", "test-api-key");
    const storage = {
      getItem: (key: string) => memoryStorage.get(key) ?? null,
      setItem: (key: string, value: string) => {
        memoryStorage.set(key, value);
      },
    };
    vi.stubGlobal("window", { localStorage: storage });
    vi.stubGlobal("localStorage", storage);
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init?: RequestInit) => {
        if (url.includes("/proposals")) {
          return {
            ok: true,
            json: async () => [{ hash: "abc", challengers: [{ name: "alpha_v2" }] }],
          };
        }
        if (url.includes("/approve")) {
          expect(init?.method).toBe("POST");
          const body = JSON.parse(String(init?.body));
          expect(body.hash).toBe("abc");
          expect(body.challenger_name).toBe("alpha_v2");
          return { ok: true, json: async () => ({ ok: true }) };
        }
        if (url.includes("/reject")) {
          const body = JSON.parse(String(init?.body));
          expect(body.reason).toBeTruthy();
          return { ok: true, json: async () => ({ ok: true }) };
        }
        return { ok: false, text: async () => "not found" };
      }),
    );
  });

  it("resolves default challenger from proposal", () => {
    const name = resolveDefaultChallengerName({
      hash: "abc",
      challengers: [{ name: "alpha_v2" }],
    });
    expect(name).toBe("alpha_v2");
  });

  it("fetches proposals with api key header", async () => {
    const rows = await fetchEvolutionProposals();
    expect(rows).toHaveLength(1);
  });

  it("posts approve payload", async () => {
    await approveProposal({ hash: "abc", challenger_name: "alpha_v2" });
  });

  it("posts reject payload", async () => {
    await rejectProposal({ hash: "abc", reason: "test reject" });
  });
});
