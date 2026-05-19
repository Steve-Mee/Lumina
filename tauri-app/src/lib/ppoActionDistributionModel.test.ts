import { describe, expect, it } from "vitest";

import {
  dominantActionSegment,
  mapActionDistributionToChartData,
} from "@/lib/ppoActionDistributionModel";

describe("ppoActionDistributionModel", () => {
  it("maps distribution to chart segments with percentages", () => {
    const segments = mapActionDistributionToChartData({ long: 0.6, short: 0.3, hold: 0.1 });
    expect(segments).toHaveLength(3);
    expect(segments[0]).toMatchObject({ key: "long", percent: 60, value: 0.6 });
    expect(segments[1]).toMatchObject({ key: "short", percent: 30, value: 0.3 });
    expect(segments[2]).toMatchObject({ key: "hold", percent: 10, value: 0.1 });
  });

  it("returns dominant action segment", () => {
    const segments = mapActionDistributionToChartData({ long: 0.2, short: 0.5, hold: 0.3 });
    expect(dominantActionSegment(segments).key).toBe("short");
  });
});
