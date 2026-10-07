import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");

function read(relativePath: string): string {
  return readFileSync(join(root, relativePath), "utf8");
}

describe("Lumina phase layout contract", () => {
  const frames = read("components/shared/PhaseCinematicFrames.tsx");
  const living = read("components/shared/LivingPhaseMission.tsx");
  const css = read("styles/birthPhase.css");

  it("Genesis start frame is helix + glass charter", () => {
    expect(frames).toContain("birth-genesis-grid");
    expect(frames).toContain("birth-genesis-helix-stage");
    expect(frames).toContain("birth-genesis-panel");
    expect(frames).toContain("lumina-glass--overlay");
    expect(css).toMatch(/\.birth-genesis-grid[\s\S]*minmax\(120px, 14%\)/);
  });

  it("one organism stage is reused across charter, mission, and Command Deck", () => {
    expect(frames).toContain("PhaseHelixStage");
    expect(living).toContain("PhaseGenesisFrame");
    expect(living).toContain("PhaseMissionFrame");
    expect(read("components/maturity/PhaseHubDeck.tsx")).toContain("PhaseGenesisFrame");
    expect(read("components/cockpit/CommandDeckScreen.tsx")).toContain("PhaseHelixStage");
  });

  it("Birth running frame is three-column mission grid", () => {
    expect(frames).toContain("birth-mission-grid");
    expect(frames).toContain('variant="mission"');
    expect(living).toContain("birth-mission-control");
    expect(living).toContain("birth-stage-intel-column");
    expect(css).toMatch(
      /\.birth-mission-grid[\s\S]*minmax\(100px, 12%\)[\s\S]*minmax\(260px, 34%\)[\s\S]*minmax\(320px, 1fr\)/,
    );
    expect(frames).toContain("lg:flex");
    expect(frames).not.toContain("lg:block");
  });

  it("Playground docks the live brief under AND gates while the clock runs", () => {
    expect(living).toContain("playground-sense-slot");
    expect(living).toContain("birth-stage-intel-column__body--dock");
    expect(read("components/maturity/PlaygroundMission.tsx")).toContain(
      'variant={running ? "dock" : "inline"}',
    );
  });

  it("living phases share the Genesis/Birth frames", () => {
    for (const path of [
      "components/maturity/AwakeningMission.tsx",
      "components/maturity/PlaygroundMission.tsx",
      "components/maturity/ApprenticeshipMission.tsx",
      "components/maturity/ProvingGroundMission.tsx",
    ]) {
      const source = read(path);
      expect(source).toContain("LivingPhaseMission");
      expect(source).not.toContain("PhaseExamStrip");
    }
  });

  it("phase start chrome uses strip header; running uses compact", () => {
    for (const path of [
      "components/maturity/AwakeningPhaseScreen.tsx",
      "components/maturity/PlaygroundPhaseScreen.tsx",
      "components/maturity/ApprenticeshipPhaseScreen.tsx",
      "components/maturity/ProvingGroundPhaseScreen.tsx",
    ]) {
      const source = read(path);
      expect(source).toContain('variant={running ? "compact" : "strip"}');
    }
    expect(read("components/maturity/PhaseHubScreen.tsx")).toContain('variant="strip"');
    expect(read("components/maturity/PhaseHubDeck.tsx")).toContain("PhaseGenesisFrame");
    expect(read("components/maturity/PhaseHubDeck.tsx")).toContain("RecoveryActionCard");
    expect(read("components/maturity/PhaseHubDeck.tsx")).toContain("CharterTile");
    expect(read("components/maturity/PhaseHubDeck.tsx")).not.toContain("BirthStagePassChecklistCard");
    expect(read("components/maturity/PhaseHubDeck.tsx")).toContain("PhaseCtaBar");
    expect(read("components/maturity/PhaseHubDeck.tsx")).not.toContain("PhaseMissionFrame");
    expect(read("components/birth/GenesisMaturityLadder.tsx")).toContain(
      "Paired CI is not this exit.",
    );
    expect(read("components/birth/GenesisMaturityLadder.tsx")).toContain("First Watch");
    expect(read("components/birth/GenesisMaturityLadder.tsx")).not.toMatch(/Lift ≥5pp/);
    expect(read("components/maturity/AwakeningMission.tsx")).toContain('panelTitle="First Watch"');
    expect(read("components/maturity/AwakeningMission.tsx")).not.toContain("Open eyes");
    expect(read("components/maturity/AwakeningPhaseScreen.tsx")).toContain('title="First Watch"');
    expect(read("components/maturity/PhaseHubDeck.tsx")).not.toContain("phase-hub-proof-row");
    expect(read("components/birth/BirthPhaseScreen.tsx")).toContain(
      'variant={missionMode && !launchingMode ? "compact" : "strip"}',
    );
  });

  it("Playground envelope seal uses the Genesis two-plane", () => {
    const seal = read("components/onboarding/PlaygroundEnvelopeSeal.tsx");
    expect(seal).toContain("PhaseGenesisFrame");
    expect(seal).toContain("OnboardingShell");
    expect(seal).toContain("LuminaPhaseHeader");
    expect(seal).toContain('variant="strip"');
  });

  it("Command Deck keeps genesis spine and glass toolbar titles", () => {
    const deck = read("components/cockpit/CommandDeckScreen.tsx");
    const evolution = read("components/cockpit/EvolutionDeckPanel.tsx");
    const intelligence = read("components/cockpit/IntelligenceDeckPanel.tsx");
    const css = read("styles/cockpit.css");
    expect(deck).toContain("command-deck-ops");
    expect(deck).toContain("PhaseHelixStage");
    expect(deck).toContain('variant="mission"');
    expect(deck).toContain("command-deck-ops__helix");
    expect(frames).toContain("helix-column-host");
    expect(frames).toContain("helix-column-fill");
    expect(read("styles/birthPhase.css")).toContain("helix-column-host");
    expect(read("styles/birthPhase.css")).toContain(
      ".birth-helix-accent-wrap:not(.helix-column-host)",
    );
    expect(deck).not.toContain("birth-genesis-grid");
    expect(deck).not.toContain("living-phase-shell");
    expect(deck).toContain("risk-envelope-panel__toolbar");
    expect(deck).toContain("command-deck-ops__hud");
    expect(deck).toContain("command-deck-ops__boards");
    expect(deck).toContain("command-deck-ops__return");
    expect(deck).toContain("CommandDeckStatusStrip");
    expect(read("components/cockpit/CommandDeckStatusStrip.tsx")).toContain("selectBarBook");
    expect(read("components/cockpit/CommandDeckStatusStrip.tsx")).toContain("BARS LOCK");
    expect(deck).toContain("CommandDeckRiskStrip");
    expect(frames).toContain("BirthHelixVisual");
    expect(evolution).toContain("risk-envelope-panel__toolbar-title");
    expect(intelligence).toContain("risk-envelope-panel__toolbar-title");
    expect(css).toContain("minmax(168px, 18%)");
    expect(css).toContain(".cockpit-shell__stage");
    expect(css).toContain(".command-deck-ops > .helix-column-host");
    expect(css).toContain("grid-template: minmax(0, 1fr) / minmax(0, 1fr)");
    expect(css).toMatch(
      /\.command-deck-ops > \.command-deck-ops__panel[\s\S]*grid-template-rows:\s*auto auto auto minmax\(0, 1fr\)/,
    );
  });

  it("Command Deck shares Genesis action language", () => {
    const deck = read("components/cockpit/CommandDeckScreen.tsx");
    const evolution = read("components/cockpit/EvolutionDeckPanel.tsx");
    const intelligence = read("components/cockpit/IntelligenceDeckPanel.tsx");
    const stage = read("components/decision/DecisionTheaterStage.tsx");
    const modeSwitch = read("components/cockpit/ModeSwitch.tsx");
    const drawer = read("components/cockpit/SubsystemsDrawer.tsx");
    const css = read("styles/cockpit.css");
    expect(deck).toContain("genesis-recovery-action-card__btn");
    expect(stage).toContain("genesis-recovery-action-card__btn");
    expect(stage).toContain("BirthKpiTile");
    expect(stage).toContain("StatusChip");
    expect(evolution).not.toContain("TabsList");
    expect(evolution).not.toContain('from "@/components/ui/tabs"');
    expect(evolution).toContain("Arena");
    expect(evolution).toContain('setActiveCenterTab("evolution")');
    expect(evolution).toContain("aria-pressed");
    expect(read("components/cockpit/IntelligenceTabContent.tsx")).not.toContain(
      'AnnexTabContent tab="performance"',
    );
    expect(read("components/cockpit/IntelligenceTabContent.tsx")).not.toContain(
      'AnnexTabContent tab="admin"',
    );
    expect(read("components/operations/AdminPanel.tsx")).not.toContain("AnalyticsAnnexShell");
    expect(read("components/operations/PhaseResetPanel.tsx")).toContain(
      "genesis-recovery-action-grid--3",
    );
    expect(css).toContain(".command-deck-ops .phase-reset-panel");
    expect(css).toContain(".command-deck-ops .phase-reset-admin");
    expect(read("components/performance/TradingPerformancePanel.tsx")).toContain("BirthKpiTile");
    expect(read("components/performance/TradingPerformancePanel.tsx")).toContain("StatusChip");
    expect(read("components/EvolutionArena.tsx")).toContain("EvolutionArenaIdle");
    expect(read("components/EvolutionArena.tsx")).toContain("command-deck-ops__arena-kpis");
    expect(css).toContain(".command-deck-ops__arena-idle");
    expect(css).toContain(".command-deck-ops__performance");
    expect(intelligence).toContain("command-deck-ops__nav");
    expect(evolution).toContain("command-deck-ops__board-chrome-row");
    expect(intelligence).toContain("command-deck-ops__board-identity");
    expect(css).toContain(".command-deck-ops__board-nav");
    expect(drawer).toContain("command-deck-ops__organ-btn");
    expect(drawer).toContain("genesis-recovery-action-card__btn--idle");
    expect(drawer).toContain("createPortal");
    expect(drawer).toContain("getLuminaOverlayRoot");
    expect(css).toContain(".subsystems-drawer-airlock");
    expect(css).toContain("position: fixed !important");
    expect(modeSwitch).toContain("mode-switch__shell");
    expect(css).toContain(".command-deck-ops .mode-switch__shell");
    expect(css).toContain(".command-deck-ops .command-hud__nt-pill");
    expect(css).toContain(".command-deck-ops .decision-theater-stage__actions");
    expect(css).toContain(".command-deck-ops__organ-btn");
  });
});
