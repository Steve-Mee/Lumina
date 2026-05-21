import { describe, expect, it } from "vitest";

import { resolveDeckStatus } from "@/lib/deckStatusOrchestrator";
import { deckTransportDotClass, deckTransportLabel } from "@/lib/deckStatusModel";

describe("deckStatusModel", () => {
  it("deckTransportLabel returns Polling when fallback active", () => {
    expect(deckTransportLabel("connected", true)).toBe("Polling");
    expect(deckTransportLabel("connected", false)).toBe("Linked");
    expect(deckTransportLabel("disconnected", false)).toBe("Offline");
  });

  it("deckTransportDotClass uses amber pulse when fallback active", () => {
    expect(deckTransportDotClass("connected", true)).toContain("animate-pulse");
    expect(deckTransportDotClass("connected", false)).toContain("emerald");
  });

  it("deckTransportDotClass tints connected dot for REAL mode", () => {
    expect(deckTransportDotClass("connected", false, "REAL")).toContain("mode-real-accent");
  });

  it("resolveDeckStatus prefers backend over fallback and welcome", () => {
    expect(
      resolveDeckStatus({
        backendDown: true,
        birthActive: false,
        fallbackActive: true,
        welcomeVisible: true,
        backendRecovered: false,
        syncPending: false,
        syncError: false,
      }).blocking,
    ).toBe("backend");
  });

  it("resolveDeckStatus orders birth before fallback and welcome", () => {
    expect(
      resolveDeckStatus({
        backendDown: false,
        birthActive: true,
        fallbackActive: true,
        welcomeVisible: true,
        backendRecovered: false,
        syncPending: false,
        syncError: false,
      }).blocking,
    ).toBe("birth");

    expect(
      resolveDeckStatus({
        backendDown: false,
        birthActive: false,
        fallbackActive: true,
        welcomeVisible: true,
        backendRecovered: false,
        syncPending: false,
        syncError: false,
      }).blocking,
    ).toBe("fallback");

    expect(
      resolveDeckStatus({
        backendDown: false,
        birthActive: false,
        fallbackActive: false,
        welcomeVisible: true,
        backendRecovered: false,
        syncPending: false,
        syncError: false,
      }).blocking,
    ).toBe("welcome");
  });

  it("resolveDeckStatus returns null blocking when nothing active", () => {
    expect(
      resolveDeckStatus({
        backendDown: false,
        birthActive: false,
        fallbackActive: false,
        welcomeVisible: false,
        backendRecovered: false,
        syncPending: false,
        syncError: false,
      }).blocking,
    ).toBeNull();
  });
});
