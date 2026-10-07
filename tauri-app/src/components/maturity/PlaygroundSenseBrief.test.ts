import { describe, expect, it } from "vitest";

import { senseLinesForScreen, senseViewForScreen } from "@/components/maturity/PlaygroundSenseBrief";

describe("PlaygroundSenseBrief", () => {
  it("labels the fallback as a fallback, not as a live measurement", () => {
    const view = senseViewForScreen(undefined, true);
    expect(view?.fallback).toBe(true);
    expect(view?.waiting).toContain("fallback");
    expect(view?.waiting.toLowerCase()).toContain("geen 240-minutenkaars nodig");
  });

  it("uses the engine fields when they are present", () => {
    const view = senseViewForScreen(
      {
        headline: "Zij kiest plat. laatste actie 0.15.",
        waiting: "Niet op een kaars. n_P telt alleen een echte fill. Nu 0/150.",
        clock: "Laatste minuut 12s geleden · Chicago 13:20",
        market: "MES DEC26 · 7775.00",
        alerts: ["Occupancy 100% plat. De poort vraagt 25–75%."],
        tone: "alert",
        pass_now: false,
      },
      true,
    );
    expect(view?.fallback).toBe(false);
    expect(view?.headline).toContain("kiest plat");
    expect(view?.market).toContain("MES DEC26");
    expect(view?.tone).toBe("alert");
    expect(view?.alerts).toHaveLength(1);
  });

  it("stays quiet when the clock is off and no brief has arrived", () => {
    expect(senseViewForScreen(undefined, false)).toBeNull();
    expect(senseLinesForScreen(undefined, false)).toEqual([]);
  });

  it("maps old line-only payloads onto the instrument", () => {
    const view = senseViewForScreen(
      { lines: ["Zij kijkt elke gesloten minuut. Een 240-minutenkaars is niet nodig om te beginnen."] },
      true,
    );
    expect(view?.headline).toContain("niet nodig om te beginnen");
    expect(view?.fallback).toBe(false);
  });
});
