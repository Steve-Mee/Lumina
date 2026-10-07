import { describe, expect, it } from "vitest";

import {
  ORGANISM_FIT_MAX,
  ORGANISM_FIT_MIN,
  organismFitDistance,
} from "@/lib/organism/organismCameraFit";

describe("organismFitDistance", () => {
  it("pulls the camera back in a tall-narrow column so the helix fits", () => {
    const square = organismFitDistance(1.7, 0.8, 1);
    const column = organismFitDistance(1.7, 0.8, 0.25);
    expect(column).toBeGreaterThan(square);
    expect(column).toBeGreaterThan(6);
    expect(column).toBeLessThanOrEqual(ORGANISM_FIT_MAX);
  });

  it("stays within the visual clamp", () => {
    expect(organismFitDistance(0.2, 0.2, 1)).toBe(ORGANISM_FIT_MIN);
    expect(organismFitDistance(40, 40, 0.1)).toBe(ORGANISM_FIT_MAX);
  });

  it("grows distance when the window aspect gets narrower", () => {
    const wide = organismFitDistance(1.7, 0.9, 0.8);
    const mid = organismFitDistance(1.7, 0.9, 0.4);
    const thin = organismFitDistance(1.7, 0.9, 0.22);
    expect(mid).toBeGreaterThan(wide);
    expect(thin).toBeGreaterThan(mid);
  });
});
