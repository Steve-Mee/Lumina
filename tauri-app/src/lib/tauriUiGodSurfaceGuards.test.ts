/**
 * Tauri UI god-surface LOC guard.
 * Façades must not grow; companions that actually exist stay ≤400.
 * Residual oversized façades are tracked at measured baselines (2026-08-11)
 * so further growth fails closed — extract before raising a ceiling.
 */
import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");

function lineCount(relativePath: string): number {
  const text = readFileSync(join(root, relativePath), "utf8");
  return text.split(/\r?\n/).length;
}

/** Declared façades — ceilings = current measured size (block growth). */
const FACADE_CEILINGS: Record<string, number> = {
  "components/birth/BirthStageScorecard.tsx": 400,
  "components/birth/BirthGenesisDeck.tsx": 796,
  "components/birth/BirthPhaseScreen.tsx": 400,
  "components/birth/BirthHelixVisual.tsx": 400,
  "components/birth/BirthHelixLegacyScene.tsx": 417,
  "components/birth/BirthAdvancedPanel.tsx": 400,
  "components/onboarding/steps/CredentialsStep.tsx": 580,
  "components/maturity/PhaseHubScreen.tsx": 405,
  "components/operations/ApprovalTwinTrainPanel.tsx": 400,
  "components/config/BotConfigForm.tsx": 400,
  "components/cockpit/CommandHud.tsx": 552,
  "components/cockpit/SettingsDialog.tsx": 433,
  "components/intelligence/SystemMonitorPanel.tsx": 400,
  "components/LivingCore.tsx": 500,
  "components/RiskCitadel.tsx": 482,
  "components/evolution/EvolutionForceGraphScene.tsx": 409,
  "store/birthStore.ts": 676,
  "store/onboardingStore.ts": 744,
  "hooks/useBirthPhaseActions.ts": 453,
  "lib/twinClient.ts": 400,
  "lib/luminaMetricsModel.ts": 400,
};

/**
 * Companions that exist today (aspirational ghosts removed — no empty stubs).
 * Default ceiling 400; residual modules call out measured baselines.
 */
const REQUIRED_COMPANIONS: Record<string, number> = {
  "components/birth/BirthStageScorecardFormat.ts": 400,
  "components/birth/BirthStageScorecardTabs.tsx": 400,
  "components/birth/BirthStageScorecardStageTab.tsx": 400,
  "components/birth/BirthStageScorecardRecoveryTab.tsx": 400,
  "components/birth/BirthStageScorecardEvolutionTab.tsx": 400,
  "components/birth/BirthGenesisStatusChips.tsx": 400,
  "components/birth/BirthHelixCeremonyScene.tsx": 400,
  "components/birth/BirthHelixScenes.tsx": 400,
  "components/onboarding/steps/CredentialsVaultPrimitives.tsx": 400,
  "components/onboarding/steps/CredentialsVaultChrome.tsx": 400,
  "components/onboarding/steps/CredentialsVaultMissionColumn.tsx": 400,
  "components/onboarding/steps/CredentialsVaultDetailPanel.tsx": 400,
  "components/onboarding/steps/CredentialsVaultDiagnosticResults.tsx": 400,
  "components/onboarding/steps/CredentialsVaultFabricPanel.tsx": 400,
  "components/onboarding/steps/CredentialsVaultTabPanels.tsx": 400,
  "components/onboarding/steps/credentialsVaultState.ts": 485,
  "components/onboarding/steps/credentialsFabricActions.ts": 400,
  "components/maturity/phaseHubFormat.ts": 400,
  "components/maturity/PhaseHubHonestyBoard.tsx": 400,
  "components/maturity/PhaseHubAdvanceSection.tsx": 400,
  "lib/twinClientTypes.ts": 400,
  "lib/twinClientCore.ts": 400,
  "lib/twinClientGym.ts": 400,
  "lib/twinClientFormat.ts": 400,
  "lib/luminaMetricsTypes.ts": 400,
  "lib/luminaMetricsNormalize.ts": 400,
};

describe("Tauri UI god-surface guards", () => {
  for (const [relativePath, ceiling] of Object.entries(FACADE_CEILINGS)) {
    it(`${relativePath} stays ≤ ${ceiling} lines`, () => {
      const count = lineCount(relativePath);
      expect(count).toBeLessThanOrEqual(ceiling);
    });
  }

  for (const [rel, ceiling] of Object.entries(REQUIRED_COMPANIONS)) {
    it(`companion exists: ${rel}`, () => {
      expect(existsSync(join(root, rel))).toBe(true);
      expect(lineCount(rel)).toBeLessThanOrEqual(ceiling);
    });
  }

  it("BirthStageScorecard façade delegates to tab modules", () => {
    const text = readFileSync(
      join(root, "components/birth/BirthStageScorecard.tsx"),
      "utf8",
    );
    expect(text).toContain("BirthStageScorecardTabs");
    expect(text).toContain("BirthStageScorecardFormat");
  });

  it("CredentialsStep façade delegates to vault panels", () => {
    const text = readFileSync(
      join(root, "components/onboarding/steps/CredentialsStep.tsx"),
      "utf8",
    );
    expect(text).toContain("CredentialsVaultMissionColumn");
    expect(text).toContain("CredentialsVaultDetailPanel");
    expect(text).toContain("credentialsFabricActions");
  });

  it("PhaseHubScreen façade embeds honesty + advance sections", () => {
    const text = readFileSync(
      join(root, "components/maturity/PhaseHubScreen.tsx"),
      "utf8",
    );
    expect(text).toContain("PhaseHubHonestyBoard");
    expect(text).toContain("PhaseHubAdvanceSection");
  });
});
