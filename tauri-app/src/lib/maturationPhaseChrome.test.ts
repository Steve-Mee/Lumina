import { describe, expect, it } from "vitest";

import {
  normalizeMaturationPhase,
  resolveChromeMaturationPhase,
} from "@/lib/maturationPhaseChrome";

describe("maturationPhaseChrome", () => {
  it("normalizes known and alias phase tokens", () => {
    expect(normalizeMaturationPhase("genesis")).toBe("genesis");
    expect(normalizeMaturationPhase("PROVING_GROUND")).toBe("proving_ground");
    expect(normalizeMaturationPhase("proving")).toBe("proving_ground");
    expect(normalizeMaturationPhase("unknown")).toBeNull();
  });

  it("maps wizard to setup and genesis birth to genesis step", () => {
    expect(
      resolveChromeMaturationPhase({ appPhase: "wizard", apiPhase: "playground" }),
    ).toBe("setup");
    expect(
      resolveChromeMaturationPhase({
        appPhase: "birth",
        birthSurface: "genesis",
        birthUiPhase: "idle",
      }),
    ).toBe("genesis");
  });

  it("maps running birth to birth step and finale to awakening", () => {
    expect(
      resolveChromeMaturationPhase({
        appPhase: "birth",
        birthSurface: "running",
        birthUiPhase: "running",
      }),
    ).toBe("birth");
    expect(
      resolveChromeMaturationPhase({
        appPhase: "birth",
        birthSurface: "running",
        birthUiPhase: "finale",
      }),
    ).toBe("awakening");
  });

  it("prefers API phase on cockpit", () => {
    expect(
      resolveChromeMaturationPhase({
        appPhase: "cockpit",
        apiPhase: "apprenticeship",
      }),
    ).toBe("apprenticeship");
    expect(resolveChromeMaturationPhase({ appPhase: "cockpit" })).toBe("playground");
  });
});
