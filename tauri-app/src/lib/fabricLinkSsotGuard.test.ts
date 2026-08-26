/**
 * Source guards: dual-truth Fabric GREEN must not regress.
 * Primary Vault color = live level; seal uses host+proof separately.
 */
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");

describe("fabric link SSOT guards", () => {
  it("CredentialsStep never aliases seal-ready to live green display", () => {
    const src = readFileSync(
      join(root, "components/onboarding/steps/CredentialsStep.tsx"),
      "utf8",
    );
    expect(src).toContain("fabricLiveGreen");
    expect(src).toContain("fabricReadyForSeal");
    expect(src).toContain("linkSummaryLive");
    expect(src).toContain("linkChipStateFromLive");
    expect(src).toContain("fetchFabricLinkStatus");
    // Dual-lie root cause: must not map seal/proof to fabricGreen display.
    expect(src).not.toMatch(
      /const fabricGreen\s*=\s*fabricReadyForSeal/,
    );
    expect(src).not.toMatch(
      /const fabricGreen\s*=\s*fabricCertified\s*\|\|/,
    );
    expect(src).toMatch(/fabricGreen=\{Boolean\(fabricLiveGreen\)\}/);
  });

  it("orchestrator rejects paper cert alone", () => {
    const src = readFileSync(
      join(root, "lib/startupSystemsOrchestrator.ts"),
      "utf8",
    );
    expect(src).toContain("hostReady");
    expect(src).toMatch(/host_ready|hostReady/);
    // Bootstrap paper green must not early-return success as live GREEN.
    expect(src).not.toMatch(
      /if \(boot && boot\.fabric_link_green\) \{\s*return \{\s*green:\s*true/,
    );
  });

  it("setupClient exposes live SSOT fields", () => {
    const src = readFileSync(join(root, "lib/setupClient.ts"), "utf8");
    expect(src).toContain("gate_birth_ok");
    expect(src).toContain("host_ready");
    expect(src).toContain("FabricLinkProof");
  });
});
