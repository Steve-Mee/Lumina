import { afterEach, describe, expect, it, vi } from "vitest";

import { readOperatorPhase, rememberOperatorPhase } from "@/lib/systemsGoSession";

describe("systemsGoSession operator phase", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("remembers a concrete phase and ignores loading", () => {
    const store = new Map<string, string>();
    vi.stubGlobal("sessionStorage", {
      getItem: (key: string) => store.get(key) ?? null,
      setItem: (key: string, value: string) => {
        store.set(key, value);
      },
    });

    rememberOperatorPhase("loading");
    expect(readOperatorPhase()).toBeNull();
    rememberOperatorPhase("awakening");
    expect(readOperatorPhase()).toBe("awakening");
  });
});
