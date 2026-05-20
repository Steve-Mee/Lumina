import { describe, expect, it } from "vitest";

import {
  getBackendAlive,
  getBackendHealthKnown,
  subscribeBackendHealth,
} from "@/lib/backendHealthStore";

describe("backendHealthStore", () => {
  it("defaults fail-closed until first probe", () => {
    expect(getBackendAlive()).toBe(false);
    expect(getBackendHealthKnown()).toBe(false);
  });

  it("notifies subscribers with current alive state", () => {
    const seen: boolean[] = [];
    const unsub = subscribeBackendHealth((alive) => seen.push(alive));
    expect(seen.length).toBeGreaterThan(0);
    expect(typeof getBackendAlive()).toBe("boolean");
    unsub();
  });
});
