import { describe, expect, it } from "vitest";

import { resolveDeckStatus } from "@/lib/deckStatusOrchestrator";

describe("deckStatusOrchestrator", () => {
  it("suppresses banner when backend is down (blocking overlay owns it)", () => {
    const resolution = resolveDeckStatus({
      backendDown: true,
      birthActive: false,
      fallbackActive: false,
      welcomeVisible: false,
      backendRecovered: false,
      syncPending: false,
      syncError: false,
    });
    expect(resolution.blocking).toBe("backend");
    expect(resolution.banner).toBeNull();
    expect(resolution.railChip).toBeNull();
  });

  it("suppresses banner when welcome overlay is active", () => {
    const resolution = resolveDeckStatus({
      backendDown: false,
      birthActive: false,
      fallbackActive: false,
      welcomeVisible: true,
      backendRecovered: false,
      syncPending: false,
      syncError: false,
    });
    expect(resolution.blocking).toBe("welcome");
    expect(resolution.banner).toBeNull();
  });

  it("shows recovery rail chip when backend recovers", () => {
    const resolution = resolveDeckStatus({
      backendDown: false,
      birthActive: false,
      fallbackActive: false,
      welcomeVisible: false,
      backendRecovered: true,
      syncPending: false,
      syncError: false,
    });
    expect(resolution.blocking).toBeNull();
    expect(resolution.railChip).toBe("recovery");
  });

  it("shows sync rail chip when mode sync pending", () => {
    const resolution = resolveDeckStatus({
      backendDown: false,
      birthActive: false,
      fallbackActive: false,
      welcomeVisible: false,
      backendRecovered: false,
      syncPending: true,
      syncError: false,
    });
    expect(resolution.railChip).toBe("sync");
    expect(resolution.suppressToast).toBe(true);
  });
});
