import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const docsRoot = join(root, "../../docs");

describe("startupReadinessSurface", () => {
  it("Systems Go cover holds until orchestrator completes (not process-only)", () => {
    const cold = readFileSync(
      join(root, "components/startup/ColdStartReadiness.tsx"),
      "utf8",
    );
    expect(cold).toContain("runSystemsGoAfterBackend");
    expect(cold).toContain("hydrateBirthSession");
    expect(cold).toContain("setFabricStartup");
    expect(cold).toContain("need_birth_retry");
    // Must NOT resolve solely because NT.exe is running
    expect(cold).not.toMatch(/if \(up\) setNtStartupResolved\(true\)/);
    expect(cold).not.toContain("closeNinjaTrader");
    const orch = readFileSync(join(root, "lib/startupSystemsOrchestrator.ts"), "utf8");
    // Degraded must not re-enter ensureFabricGreen wait
    expect(orch).toMatch(/if \(degraded\) \{[\s\S]*Operator continued without live Fabric GREEN/);
    expect(orch).toContain("need_birth_retry");
  });

  it("OnboardingGate holds cover until systems ready", () => {
    const gate = readFileSync(
      join(root, "components/onboarding/OnboardingGate.tsx"),
      "utf8",
    );
    expect(gate).toContain("ColdStartReadiness");
    expect(gate).toContain("ntStartupResolved");
    expect(gate).toContain("holdForNtGate");
  });

  it("Birth monitor skips cold probe when session already hydrated", () => {
    const mon = readFileSync(join(root, "hooks/useBirthPhaseMonitor.ts"), "utf8");
    expect(mon).toContain("sessionHydrated");
    expect(mon).toMatch(/already[\s\S]*return/);
  });

  it("Credentials reuses cold-start fabricStartup", () => {
    const creds = readFileSync(
      join(root, "components/onboarding/steps/CredentialsStep.tsx"),
      "utf8",
    );
    expect(creds).toContain("fabricStartup");
    expect(creds).toMatch(/fabricStartup\?\.green/);
  });

  it("runbook documents Systems Go / one clean wait", () => {
    const runbook = readFileSync(
      join(docsRoot, "command-deck-startup-runbook.md"),
      "utf8",
    );
    expect(runbook).toContain("StartupReadinessScreen");
    expect(runbook).toMatch(/NinjaTrader process|Systems Go|maturation_hub/i);
  });

  it("Systems Go UI uses compact centered window + vault language", () => {
    const screen = readFileSync(
      join(root, "components/startup/StartupReadinessScreen.tsx"),
      "utf8",
    );
    expect(screen).toContain("OnboardingShell");
    expect(screen).toContain("CredentialsVaultOrganism");
    expect(screen).toContain("systems-go-viewport");
    expect(screen).toContain("systems-go-window");
    expect(screen).toContain("systems-go-panel");
    expect(screen).toContain("SystemsGoDialog");
    expect(screen).toContain("credentials-vault-status-chip");
    expect(screen).toContain("data-active");
    expect(screen).toMatch(/state === "done"[\s\S]*return "ok"/);
    const cold = readFileSync(
      join(root, "components/startup/ColdStartReadiness.tsx"),
      "utf8",
    );
    // Hold final all-green paint before leaving cover
    expect(cold).toMatch(/ALL_GREEN_HOLD_MS|1250/);
    const css = readFileSync(join(root, "styles/onboarding.css"), "utf8");
    expect(css).toContain(".systems-go-viewport");
    expect(css).toContain(".systems-go-window");
    expect(css).toContain(".systems-go-step");
    expect(css).toContain(".systems-go-dialog");
    expect(css).toContain(".systems-go-step[data-active=\"true\"]");
    expect(css).toContain("var(--status-ok");
    expect(css).toContain("var(--status-partial");
    expect(css).toContain("var(--status-fail");
  });
});



