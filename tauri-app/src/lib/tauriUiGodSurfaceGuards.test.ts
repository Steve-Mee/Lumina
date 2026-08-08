/**
 * Tauri UI god-surface LOC guard (deep-research residual wave).
 * Declared façades must stay ≤400 lines; companions must exist.
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

/** Declared residual UI + store/HUD façades (must stay ≤400). */
const FACADE_CEILINGS: Record<string, number> = {
  "components/birth/BirthStageScorecard.tsx": 400,
  "components/birth/BirthGenesisDeck.tsx": 400,
  "components/birth/BirthPhaseScreen.tsx": 400,
  "components/birth/BirthHelixVisual.tsx": 400,
  "components/birth/BirthHelixLegacyScene.tsx": 400,
  "components/birth/BirthAdvancedPanel.tsx": 400,
  "components/onboarding/steps/CredentialsStep.tsx": 400,
  "components/maturity/PhaseHubScreen.tsx": 400,
  "components/operations/ApprovalTwinTrainPanel.tsx": 400,
  "components/config/BotConfigForm.tsx": 400,
  "components/cockpit/CommandHud.tsx": 400,
  "components/cockpit/SettingsDialog.tsx": 400,
  "components/intelligence/SystemMonitorPanel.tsx": 400,
  "components/LivingCore.tsx": 400,
  "components/RiskCitadel.tsx": 400,
  "components/evolution/EvolutionForceGraphScene.tsx": 400,
  "store/birthStore.ts": 400,
  "store/onboardingStore.ts": 400,
  "hooks/useBirthPhaseActions.ts": 400,
  "lib/twinClient.ts": 400,
  "lib/luminaMetricsModel.ts": 400,
};

const REQUIRED_COMPANIONS = [
  "components/birth/BirthStageScorecardFormat.ts",
  "components/birth/BirthStageScorecardTabs.tsx",
  "components/birth/BirthStageScorecardStageTab.tsx",
  "components/birth/BirthStageScorecardRecoveryTab.tsx",
  "components/birth/BirthStageScorecardEvolutionTab.tsx",
  "components/birth/BirthGenesisDeckPrimitives.tsx",
  "components/birth/BirthGenesisRecoveryTab.tsx",
  "components/birth/BirthHelixLegacyParts.tsx",
  "components/onboarding/steps/CredentialsVaultPrimitives.tsx",
  "components/onboarding/steps/CredentialsVaultTabPanels.tsx",
  "components/onboarding/steps/CredentialsVaultChrome.tsx",
  "components/onboarding/steps/credentialsVaultState.ts",
  "components/onboarding/steps/credentialsFabricActions.ts",
  "components/maturity/phaseHubFormat.ts",
  "components/maturity/PhaseHubHonestyBoard.tsx",
  "components/maturity/PhaseHubAdvanceSection.tsx",
  "components/cockpit/CommandHudDialogs.tsx",
  "components/cockpit/commandHudOverflow.tsx",
  "components/cockpit/commandHudFormat.ts",
  "components/cockpit/SettingsDialogChrome.tsx",
  "components/LivingCoreScene.tsx",
  "components/RiskCitadelParts.tsx",
  "components/evolution/EvolutionForceGraphParts.tsx",
  "store/birthStoreApplyStatus.ts",
  "store/birthStoreSessionActions.ts",
  "store/onboardingDraft.ts",
  "store/onboardingLifecycleActions.ts",
  "hooks/birthPhaseActionHandlers.ts",
  "lib/twinClientTypes.ts",
  "lib/twinClientCore.ts",
  "lib/twinClientGym.ts",
  "lib/twinClientFormat.ts",
  "lib/luminaMetricsTypes.ts",
  "lib/luminaMetricsNormalize.ts",
];

describe("Tauri UI god-surface guards", () => {
  for (const [relativePath, ceiling] of Object.entries(FACADE_CEILINGS)) {
    it(`${relativePath} stays ≤ ${ceiling} lines`, () => {
      const count = lineCount(relativePath);
      expect(count).toBeLessThanOrEqual(ceiling);
    });
  }

  for (const rel of REQUIRED_COMPANIONS) {
    it(`companion exists: ${rel}`, () => {
      expect(existsSync(join(root, rel))).toBe(true);
      expect(lineCount(rel)).toBeLessThanOrEqual(400);
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
    expect(text).toContain("CredentialsVaultTabPanels");
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
