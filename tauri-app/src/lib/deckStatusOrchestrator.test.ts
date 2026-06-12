import { describe, expect, it } from "vitest";

import { resolveDeckStatus } from "@/lib/deckStatusOrchestrator";

describe("deckStatusOrchestrator", () => {
  it("returns blocking backend and suppresses toast when backend is down", () => {
    const resolution = resolveDeckStatus({
      backendDown: true,
      birthActive: false,
      birthIncomplete: false,
      fallbackActive: false,
      welcomeVisible: false,
      backendRecovered: false,
      syncPending: false,
      syncError: false,
    });
    expect(resolution.blocking).toBe("backend");
    expect(resolution.railChip).toBeNull();
    expect(resolution.suppressToast).toBe(true);
  });

  it("returns blocking birth_incomplete when birth artifacts missing", () => {
    const resolution = resolveDeckStatus({
      backendDown: false,
      birthActive: false,
      birthIncomplete: true,
      fallbackActive: false,
      welcomeVisible: false,
      backendRecovered: false,
      syncPending: false,
      syncError: false,
    });
    expect(resolution.blocking).toBe("birth_incomplete");
    expect(resolution.railChip).toBeNull();
  });

  it("returns blocking welcome when welcome overlay is active", () => {
    const resolution = resolveDeckStatus({
      backendDown: false,
      birthActive: false,
      birthIncomplete: false,
      fallbackActive: false,
      welcomeVisible: true,
      backendRecovered: false,
      syncPending: false,
      syncError: false,
    });
    expect(resolution.blocking).toBe("welcome");
    expect(resolution.railChip).toBeNull();
  });

  it("shows recovery rail chip when backend recovers", () => {
    const resolution = resolveDeckStatus({
      backendDown: false,
      birthActive: false,
      birthIncomplete: false,
      fallbackActive: false,
      welcomeVisible: false,
      backendRecovered: true,
      syncPending: false,
      syncError: false,
    });
    expect(resolution.blocking).toBeNull();
    expect(resolution.railChip).toBe("recovery");
    expect(resolution.suppressToast).toBe(true);
  });

  it("does not expose sync rail chip when mode sync pending", () => {
    const resolution = resolveDeckStatus({
      backendDown: false,
      birthActive: false,
      birthIncomplete: false,
      fallbackActive: false,
      welcomeVisible: false,
      backendRecovered: false,
      syncPending: true,
      syncError: false,
    });
    expect(resolution.railChip).toBeNull();
    expect(resolution.suppressToast).toBe(true);
  });

  it("allows sync error toast when sync is not pending", () => {
    const resolution = resolveDeckStatus({
      backendDown: false,
      birthActive: false,
      birthIncomplete: false,
      fallbackActive: false,
      welcomeVisible: false,
      backendRecovered: false,
      syncPending: false,
      syncError: true,
    });
    expect(resolution.railChip).toBeNull();
    expect(resolution.suppressToast).toBe(false);
  });
});
