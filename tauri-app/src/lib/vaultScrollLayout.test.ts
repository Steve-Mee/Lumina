import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");

const onboardingCss = readFileSync(join(root, "styles/onboarding.css"), "utf8");
const credentialsStep = readFileSync(
  join(root, "components/onboarding/steps/CredentialsStep.tsx"),
  "utf8",
);
const mission = readFileSync(
  join(root, "components/onboarding/steps/CredentialsVaultMissionColumn.tsx"),
  "utf8",
);
const detail = readFileSync(
  join(root, "components/onboarding/steps/CredentialsVaultDetailPanel.tsx"),
  "utf8",
);

describe("vaultScrollLayout", () => {
  it("uses a three-column mission grid on large screens", () => {
    expect(onboardingCss).toMatch(
      /\.credentials-vault-grid[\s\S]*@media \(min-width: 1024px\)[\s\S]*grid-template-columns:[\s\S]*minmax\(110px, 16%\)[\s\S]*minmax\(280px, 36%\)[\s\S]*minmax\(300px, 1fr\)/,
    );
    expect(credentialsStep).toContain("CredentialsVaultMissionColumn");
    expect(credentialsStep).toContain("CredentialsVaultDetailPanel");
  });

  it("keeps status strip in mission column (Birth-style HUD)", () => {
    expect(mission).toContain("CredentialsVaultStatusStrip");
    expect(mission).toContain("credentials-vault-diag-card");
    expect(mission).toContain("Test connection");
    expect(mission).toContain("credentials-vault-cta-bar");
  });

  it("scrolls only detail body for long diagnostic results", () => {
    expect(onboardingCss).toMatch(
      /\.credentials-vault-detail__body[\s\S]*overflow-y:\s*auto/,
    );
    expect(onboardingCss).toMatch(
      /\.credentials-vault-detail__body[\s\S]*min-height:\s*0/,
    );
    expect(detail).toContain("credentials-vault-detail__body");
    expect(detail).toContain("CredentialsVaultDiagnosticResults");
  });

  it("centers organism in stage cell", () => {
    expect(onboardingCss).toMatch(
      /\.credentials-vault-stage[\s\S]*justify-content:\s*center/,
    );
    expect(onboardingCss).toMatch(
      /\.credentials-vault-stage[\s\S]*align-items:\s*center/,
    );
    expect(onboardingCss).toContain(
      ".credentials-vault-stage .credentials-vault-organism",
    );
  });

  it("uses field-level focus rows not abstract channel tabs", () => {
    expect(mission).toContain("credentials-vault-focus-row");
    expect(mission).toContain("Fabric diagnostic");
    expect(mission).toContain("fabricRows");
    expect(credentialsStep).not.toContain("credentials-vault-tab-list");
    expect(credentialsStep).not.toContain("TabsList");
  });

  it("uses traffic-light status tokens for ok/partial/fail", () => {
    expect(onboardingCss).toContain("var(--status-ok-border)");
    expect(onboardingCss).toContain("var(--status-partial-border)");
    expect(onboardingCss).toContain("var(--status-fail-border)");
  });
});
