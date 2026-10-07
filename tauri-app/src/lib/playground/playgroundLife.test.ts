import { describe, expect, it } from "vitest";

import {
  playgroundLifeCaption,
  playgroundLifeLine,
  resolvePlaygroundLifeState,
} from "@/lib/playground/playgroundLife";

const now = Date.parse("2026-09-28T05:26:10.000Z");

describe("playgroundLife", () => {
  it("names the missing floor while the heartbeat is fresh", () => {
    const input = {
      running: true,
      updatedAt: "2026-09-28T05:26:08.000Z",
      nP: 0,
      envelopeSealed: false,
      nowMs: now,
    };
    expect(resolvePlaygroundLifeState(input)).toBe("waiting");
    expect(playgroundLifeCaption("waiting")).toBe("School · geen drawdown-limiet");
    expect(playgroundLifeLine(input)).toContain("-2%");
    expect(playgroundLifeLine(input)).toContain("groen 0/5");
    expect(
      playgroundLifeLine({ ...input, exchangeNote: "Beurs dicht tot 18:00 ET. Geen stall. Geen order." }),
    ).toContain("Beurs dicht");
    expect(playgroundLifeLine(input)).toContain("hartslag");
  });

  it("calls a silent clock silent", () => {
    const input = {
      running: true,
      updatedAt: "2026-09-28T05:20:00.000Z",
      nP: 0,
      envelopeSealed: true,
      nowMs: now,
    };
    expect(resolvePlaygroundLifeState(input)).toBe("silent");
    expect(playgroundLifeCaption("silent")).toContain("stil");
  });

  it("shows a live crawl with the feed note", () => {
    const input = {
      running: true,
      updatedAt: "2026-09-28T05:26:09.000Z",
      nP: 3,
      envelopeSealed: true,
      feedNote: "Live prijs 5124.25. De kruip ziet de markt.",
      nowMs: now,
    };
    expect(resolvePlaygroundLifeState(input)).toBe("live");
    expect(playgroundLifeLine(input)).toContain("closes 3");
    expect(playgroundLifeLine(input)).toContain("5124.25");
  });
});
