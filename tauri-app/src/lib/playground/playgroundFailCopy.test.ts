import { describe, expect, it } from "vitest";

import {
  isPlaygroundFailed,
  playgroundClockButtonLabel,
  playgroundHeaderStatus,
  playgroundMissionMessage,
} from "@/lib/playground/playgroundFailCopy";

describe("playgroundFailCopy", () => {
  it("does not keep a loading line after the runner has died", () => {
    const input = {
      running: false,
      focusStatus: "failed",
      error: "SIM envelope breached",
      progressMessage: "Loading playground habitat",
    };
    expect(isPlaygroundFailed(input)).toBe(true);
    expect(playgroundHeaderStatus(input)).toBe(
      "Clock halted — fail-closed, Birth + Awakening intact",
    );
    expect(playgroundMissionMessage(input)).toContain("SIM envelope breached");
    expect(playgroundMissionMessage(input)).not.toContain("Loading playground");
  });

  it("keeps the live progress line while the clock is running", () => {
    const input = {
      running: true,
      progressMessage: "Crawling in NT SIM — n_P 42",
      error: null,
      focusStatus: "running",
    };
    expect(playgroundHeaderStatus(input)).toContain("n_P 42");
    expect(playgroundMissionMessage(input)).toContain("n_P 42");
    expect(playgroundClockButtonLabel({ running: true, passNow: false, progressMessage: "School · groen 0/5 · closes 42" })).toBe(
      "SCHOOL",
    );
  });

  it("does not call a flat policy a crawl", () => {
    const label = playgroundClockButtonLabel({
      running: true,
      passNow: false,
      progressMessage: "Verse bars: flat. Actie 0.12. n_P 0/150. Geen stall. Geen pass.",
    });
    expect(label).toBe("ZIJ KIEST FLAT");
  });
});
