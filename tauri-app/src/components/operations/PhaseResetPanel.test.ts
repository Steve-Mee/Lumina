import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const root = join(dirname(fileURLToPath(import.meta.url)));

function source(name: string): string {
  return readFileSync(join(root, name), "utf8");
}

describe("Command Deck phase reset", () => {
  it("Admin Panel mounts named phase reset under Subsystems", () => {
    const admin = source("AdminPanel.tsx");
    expect(admin).toContain("PhaseResetPanel");
    expect(admin).not.toContain("window.confirm");
    expect(admin).not.toContain("AnalyticsAnnexShell");
    expect(admin).toContain("phase-reset-admin");
    expect(admin).toContain("Setup snapshot");
    expect(admin).toContain("Data maintenance");
    expect(admin).toContain("First-boot reset");
    expect(admin).toContain("<details");
  });

  it("PhaseResetPanel uses hub named wipes and typed confirm", () => {
    const panel = source("PhaseResetPanel.tsx");
    expect(panel).toContain("HUB_WIPE_CARDS");
    expect(panel).toContain("PhaseHubWipeConfirm");
    expect(panel).toContain("postWipeMaturityPhase");
    expect(panel).toContain("postWipeAllMaturation");
    expect(panel).not.toContain("window.confirm");
    expect(panel).toContain("Phase reset is SIM-only");
    expect(panel).toContain("Stop the running phase before wipe");
    expect(panel).toContain("Hub unreachable — wipe stays locked");
    expect(panel).toContain("phase-reset-panel");
    expect(panel).toContain("genesis-recovery-action-grid--3");
  });
});
