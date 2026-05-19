import { describe, expect, it } from "vitest";

import {
  shouldArmSafeModeTimer,
  shouldShowSafeModeOverlay,
} from "@/lib/realSafeMode";

describe("realSafeMode", () => {
  it("arms timer when REAL and not connected", () => {
    expect(shouldArmSafeModeTimer("REAL", "reconnecting")).toBe(true);
    expect(shouldArmSafeModeTimer("REAL", "disconnected")).toBe(true);
    expect(shouldArmSafeModeTimer("REAL", "connecting")).toBe(true);
  });

  it("does not arm timer in SIM mode", () => {
    expect(shouldArmSafeModeTimer("SIM", "reconnecting")).toBe(false);
    expect(shouldArmSafeModeTimer("SIM", "disconnected")).toBe(false);
  });

  it("does not arm timer when connected", () => {
    expect(shouldArmSafeModeTimer("REAL", "connected")).toBe(false);
    expect(shouldArmSafeModeTimer("SIM", "connected")).toBe(false);
  });

  it("shows overlay only for REAL safe mode", () => {
    expect(shouldShowSafeModeOverlay("REAL", true)).toBe(true);
    expect(shouldShowSafeModeOverlay("REAL", false)).toBe(false);
    expect(shouldShowSafeModeOverlay("SIM", true)).toBe(false);
  });
});
