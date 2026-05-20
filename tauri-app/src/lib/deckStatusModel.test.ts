import { describe, expect, it } from "vitest";

import {
  blockingOverlayPriority,
  deckSyncNote,
  deckTransportDotClass,
  deckTransportLabel,
} from "@/lib/deckStatusModel";

describe("deckStatusModel", () => {
  it("deckTransportLabel returns Polling when fallback active", () => {
    expect(deckTransportLabel("connected", true)).toBe("Polling");
    expect(deckTransportLabel("connected", false)).toBe("Live");
    expect(deckTransportLabel("disconnected", false)).toBe("Offline");
  });

  it("deckTransportDotClass uses amber pulse when fallback active", () => {
    expect(deckTransportDotClass("connected", true)).toContain("animate-pulse");
    expect(deckTransportDotClass("connected", false)).toContain("emerald");
  });

  it("deckSyncNote reflects sync state", () => {
    expect(deckSyncNote("pending", null)).toBe("· syncing…");
    expect(deckSyncNote("error", "timeout")).toBe("· timeout");
    expect(deckSyncNote("error", null)).toBe("· sync failed");
    expect(deckSyncNote("idle", null)).toBeNull();
  });

  it("blockingOverlayPriority prefers backend over fallback", () => {
    expect(
      blockingOverlayPriority({
        backendDown: true,
        birthActive: false,
        fallbackActive: true,
        welcomeVisible: true,
      }),
    ).toBe("backend");
  });

  it("blockingOverlayPriority orders birth before fallback and welcome", () => {
    expect(
      blockingOverlayPriority({
        backendDown: false,
        birthActive: true,
        fallbackActive: true,
        welcomeVisible: true,
      }),
    ).toBe("birth");

    expect(
      blockingOverlayPriority({
        backendDown: false,
        birthActive: false,
        fallbackActive: true,
        welcomeVisible: true,
      }),
    ).toBe("fallback");

    expect(
      blockingOverlayPriority({
        backendDown: false,
        birthActive: false,
        fallbackActive: false,
        welcomeVisible: true,
      }),
    ).toBe("welcome");
  });

  it("blockingOverlayPriority returns null when nothing active", () => {
    expect(
      blockingOverlayPriority({
        backendDown: false,
        birthActive: false,
        fallbackActive: false,
        welcomeVisible: false,
      }),
    ).toBeNull();
  });
});
