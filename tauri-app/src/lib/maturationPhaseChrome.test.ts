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

  it("maps proving_ground app phase to proving_ground rung", () => {
    expect(
      resolveChromeMaturationPhase({ appPhase: "proving_ground", apiPhase: "apprenticeship" }),
    ).toBe("proving_ground");
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

  it("maps awakening app phase to awakening step", () => {
    expect(
      resolveChromeMaturationPhase({ appPhase: "awakening", apiPhase: "birth" }),
    ).toBe("awakening");
  });

  it("maps playground app phase to playground step", () => {
    expect(
      resolveChromeMaturationPhase({ appPhase: "playground", apiPhase: "awakening" }),
    ).toBe("playground");
  });

  it("maps apprenticeship app phase to apprenticeship step", () => {
    expect(
      resolveChromeMaturationPhase({ appPhase: "apprenticeship", apiPhase: "playground" }),
    ).toBe("apprenticeship");
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
