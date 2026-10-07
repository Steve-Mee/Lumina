import { describe, expect, it } from "vitest";

import {
  applyProbeVerdict,
  getBackendAlive,
  getBackendHealthKnown,
  subscribeBackendHealth,
} from "@/lib/backendHealthStore";

const unknown = { alive: false, known: false, hardDownStreak: 0 };
const up = { alive: true, known: true, hardDownStreak: 0 };

describe("applyProbeVerdict", () => {
  it("a timeout while the backend is up does not lock the deck", () => {
    expect(applyProbeVerdict(up, "timeout")).toEqual(up);
  });

  it("one refused connection does not declare the backend dead", () => {
    expect(applyProbeVerdict(up, "down")).toEqual({
      alive: true,
      known: true,
      hardDownStreak: 1,
    });
  });

  it("two refused connections lock the deck", () => {
    const once = applyProbeVerdict(up, "down");
    expect(applyProbeVerdict(once, "down")).toEqual({
      alive: false,
      known: true,
      hardDownStreak: 2,
    });
  });

  it("a timeout before the first answer stays unknown", () => {
    expect(applyProbeVerdict(unknown, "timeout")).toEqual(unknown);
  });
});

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
