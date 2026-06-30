import { readFileSync } from "node:fs";

import { dirname, join } from "node:path";

import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";



const birthPhaseSource = readFileSync(

  join(dirname(fileURLToPath(import.meta.url)), "../components/birth/BirthPhaseScreen.tsx"),

  "utf8",

);



const birthActivateSource = readFileSync(

  join(

    dirname(fileURLToPath(import.meta.url)),

    "../components/onboarding/steps/BirthActivateStep.tsx",

  ),

  "utf8",

);



const birthGenesisDeckSource = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), "../components/birth/BirthGenesisDeck.tsx"),
  "utf8",
);

const genesisMaturityLadderSource = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), "../components/birth/GenesisMaturityLadder.tsx"),
  "utf8",
);

const birthControlDockSource = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), "../components/birth/BirthControlDock.tsx"),
  "utf8",
);

const birthCommandBarSource = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), "../components/birth/BirthCommandBar.tsx"),
  "utf8",
);

const birthMissionControlSource = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), "../components/birth/BirthMissionControl.tsx"),
  "utf8",
);

const birthStageIntelSource = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), "../components/birth/BirthStageIntelColumn.tsx"),
  "utf8",
);

const birthAdvancedPanelSource = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), "../components/birth/BirthAdvancedPanel.tsx"),
  "utf8",
);

const birthPhaseCssSource = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), "../styles/birthPhase.css"),
  "utf8",
);



const onboardingShellSource = readFileSync(

  join(dirname(fileURLToPath(import.meta.url)), "../components/onboarding/OnboardingShell.tsx"),

  "utf8",

);



const backendStepSource = readFileSync(

  join(dirname(fileURLToPath(import.meta.url)), "../components/onboarding/steps/BackendStep.tsx"),

  "utf8",

);



const commandHudSource = readFileSync(

  join(dirname(fileURLToPath(import.meta.url)), "../components/cockpit/CommandHud.tsx"),

  "utf8",

);



const birthWizardCssSource = readFileSync(

  join(dirname(fileURLToPath(import.meta.url)), "../styles/birthWizard.css"),

  "utf8",

);



const birthCinematicLayoutSource = readFileSync(

  join(dirname(fileURLToPath(import.meta.url)), "../components/birth/BirthCinematicLayout.tsx"),

  "utf8",

);



const onboardingWizardSource = readFileSync(

  join(dirname(fileURLToPath(import.meta.url)), "../components/onboarding/OnboardingWizard.tsx"),

  "utf8",

);



const cockpitShellSource = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), "../components/cockpit/CockpitShell.tsx"),
  "utf8",
);

const luminaPhaseHeaderSource = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), "../components/shared/LuminaPhaseHeader.tsx"),
  "utf8",
);

const luminaPhaseHeaderCssSource = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), "../styles/luminaPhaseHeader.css"),
  "utf8",
);



describe("onboarding surface contracts", () => {

  it("Birth finale shows mission control and command deck entry on main screen", () => {
    expect(birthPhaseSource).toContain("Birth complete");
    expect(birthPhaseSource).not.toContain("CheckCircle2");
    expect(birthPhaseSource).not.toContain("birth-finale-hero");
    expect(birthPhaseSource).toContain("BirthMissionControl");
    expect(birthCommandBarSource).toContain("Enter command deck");
    expect(birthPhaseSource).toContain("onEnterDeck={enterCommandDeck}");
  });



  it("Birth running uses mission control dashboard on main viewport", () => {
    expect(birthPhaseSource).toContain("birth-mission-shell");
    expect(birthPhaseSource).toContain("BirthMissionControl");
    expect(birthPhaseSource).toContain("onboarding-shell--form");
    expect(birthMissionControlSource).toContain("BirthMetricsStrip");
    expect(birthMissionControlSource).toContain("embedded");
    expect(birthMissionControlSource).not.toContain("BirthMilestoneTrack");
    expect(birthCommandBarSource).toContain('variant="bar"');
    expect(birthPhaseSource).not.toContain("BirthDiagnosticsDrawer");
  });



  it("Birth mission control uses viewport-fixed layout with three-column grid", () => {
    expect(birthPhaseCssSource).toContain(".birth-mission-grid > *");
    expect(birthPhaseCssSource).toContain("min-height: 0");
    expect(birthPhaseCssSource).toMatch(
      /\.birth-mission-grid[\s\S]*@media \(min-width: 1024px\)[\s\S]*grid-template-columns:[\s\S]*minmax\(120px, 14%\)[\s\S]*minmax\(280px, 36%\)[\s\S]*minmax\(320px, 1fr\)/,
    );
    expect(birthPhaseCssSource).toContain(".birth-stage-intel-column__body");
    expect(birthPhaseCssSource).toMatch(/\.birth-stage-intel-column__body[\s\S]*overflow-y:\s*auto/);
    expect(birthPhaseSource).toContain("BirthStageIntelColumn");
    expect(birthMissionControlSource).toContain("overflow-hidden");
    expect(birthMissionControlSource).not.toContain("birth-mission-control__scroll");
  });



  it("Birth stage intel column shows scorecard and controlled advanced panel", () => {
    expect(birthMissionControlSource).not.toContain("BirthStageDetailsPanel");
    expect(birthStageIntelSource).toContain("BirthStageScorecard");
    expect(birthStageIntelSource).toContain("BirthAdvancedPanel");
    expect(birthStageIntelSource).toContain("controlled={running}");
    expect(birthMissionControlSource).toContain("BirthBlockerAlert");
    expect(birthAdvancedPanelSource).toContain("controlled?: boolean");
    expect(birthAdvancedPanelSource).toContain("birth-advanced-panel--controlled");
  });



  it("Birth helix accent column centers helix vertically on large screens", () => {
    expect(birthPhaseCssSource).toMatch(/\.birth-helix-accent-wrap[\s\S]*align-items:\s*center/);
    expect(birthPhaseCssSource).toMatch(/\.birth-helix-accent-wrap[\s\S]*justify-content:\s*center/);
    expect(birthPhaseCssSource).toContain(".birth-stage-intel-column__body::-webkit-scrollbar-track");
  });



  it("Birth command bar exposes stop and inline advanced toggles", () => {
    expect(birthPhaseSource).toContain("BirthCommandBar");
    expect(birthCommandBarSource).toContain("BirthControlDock");
    expect(birthControlDockSource).toContain("Stop birth");
    expect(birthCommandBarSource).toContain("Logs");
    expect(birthCommandBarSource).not.toContain("Telemetry");
  });



  it("Birth running uses full-viewport height without min-h-screen overflow", () => {

    expect(birthPhaseSource).toContain("h-dvh");

    expect(birthPhaseSource).not.toContain("min-h-screen");

    expect(birthPhaseSource).toContain("overflow-hidden");

    expect(birthPhaseSource).toContain("birth-mission-grid");

  });



  it("Birth genesis uses mission shell grid with helix glow stage and charter panel", () => {
    expect(birthPhaseSource).toContain("birth-mission-shell");
    expect(birthPhaseSource).toContain("birth-genesis-grid");
    expect(birthPhaseSource).toContain("birth-genesis-helix-stage");
    expect(birthPhaseSource).toContain("birth-activation-helix-arena");
    expect(birthPhaseSource).toContain("birth-genesis-panel");
    expect(birthPhaseSource).toContain("LuminaPhaseHeader");
    expect(birthPhaseSource).toContain("resolveBirthScreenPhaseHeader");
    expect(birthPhaseSource).not.toMatch(/genesisMode[\s\S]*BirthCinematicLayout/);
    expect(birthCommandBarSource).not.toMatch(/mode === "genesis"[\s\S]*BirthControlDock/);
    expect(birthCommandBarSource).not.toContain("headline");
    expect(birthCommandBarSource).toMatch(
      /showMilestoneRail\s*=\s*mode === "running" \|\| mode === "finale"/,
    );
    expect(birthGenesisDeckSource).toContain("showStartButton={false}");
    expect(birthPhaseCssSource).toContain(".birth-genesis-grid");
    expect(birthPhaseCssSource).toMatch(/\.birth-genesis-grid[\s\S]*minmax\(120px, 14%\)/);
    expect(birthPhaseCssSource).toContain(".birth-genesis-tab-panel");
    expect(birthPhaseCssSource).toContain(".birth-genesis-panel__hero");
  });



  it("Birth advanced panels stay inline in stage intel column", () => {

    expect(birthStageIntelSource).toContain("BirthAdvancedPanel");

    expect(birthAdvancedPanelSource).toContain("BirthLogsPanel");

  });



  it("BirthGenesisDeck uses tabs for goals and parameters without page scroll", () => {
    expect(birthGenesisDeckSource).toContain('value="doelen"');
    expect(birthGenesisDeckSource).toContain('value="parameters"');
    expect(birthGenesisDeckSource).not.toContain("genesisOpen");
    expect(birthGenesisDeckSource).not.toContain("birth-activation-title");
    expect(birthGenesisDeckSource).toContain("stage1_winrate_pass_threshold");
    expect(birthGenesisDeckSource).toContain("require_real_simulator_data");
    expect(birthGenesisDeckSource).toContain("Max Historical Days");
    expect(birthGenesisDeckSource).toContain("firstBootSizing");
    expect(birthGenesisDeckSource).toContain("FIRST_BOOT_MAX_REAL_DAYS");
    expect(birthGenesisDeckSource).toContain("handleTrainingTradesChange");
    expect(birthGenesisDeckSource).toContain("linkMaxRealDaysToTrainingTrades");
    expect(birthGenesisDeckSource).toContain("FIRST_BOOT_MIN_REAL_DAYS");
    const heroSection = birthGenesisDeckSource.split("birth-genesis-panel__tabs")[0] ?? "";
    expect(heroSection).toContain("Training Trades");
    expect(heroSection).toContain("GenesisWinrateGateBlock");
    expect(birthGenesisDeckSource).toContain("GenesisMaturityGoalsPreview");
    expect(genesisMaturityLadderSource).toContain("genesis-maturity-goals");
    expect(birthPhaseCssSource).toContain(".genesis-maturity-goals");
    expect(birthGenesisDeckSource).toContain("birth-genesis-tab-panel");
  });



  it("OnboardingShell omits deck vignette on birth screen", () => {

    expect(onboardingShellSource).toContain("birth-phase-screen");

    expect(onboardingShellSource).toContain("hideDeckVignette");

  });



  it("CommandHud exposes Save & Start when engine is off", () => {

    expect(commandHudSource).toContain("realTradingEligible");
    expect(commandHudSource).toContain("MaturityProgressStrip");

    expect(commandHudSource).toContain("HudNerveTap");

    expect(commandHudSource).toContain("botConfigDirty()");

  });



  it("Birth running phase can flash REAL grammar veil at milestones", () => {

    expect(birthPhaseSource).toContain("milestoneVeilActive");

    expect(birthPhaseSource).toContain('milestone.id === "refinement"');

    expect(birthPhaseSource).toContain('milestone.id === "strategies"');

    expect(birthPhaseSource).toContain('targetMode="REAL"');

  });



  it("onboarding steps use luminaSurfaceMutedClass instead of flat bg-black/20", () => {

    expect(backendStepSource).toContain("luminaSurfaceMutedClass");

    expect(backendStepSource).not.toContain("bg-black/20");

  });



  it("birth activation layout avoids viewport calc height and clips overflow", () => {

    expect(birthCinematicLayoutSource).not.toContain("100vh");

    expect(birthCinematicLayoutSource).toContain("min-h-0");

    expect(birthCinematicLayoutSource).toContain("h-full");

    expect(birthCinematicLayoutSource).not.toContain("basis-[85%]");

    expect(birthCinematicLayoutSource).toContain("birth-activation-stack");

    expect(birthCinematicLayoutSource).toContain("birth-activation-screen--anchored");

    expect(birthCinematicLayoutSource).toContain("birth-activation-helix-arena");

    expect(birthWizardCssSource).toContain("overflow-x: clip");

    expect(birthWizardCssSource).toMatch(
      /\.birth-activation-stack[\s\S]*grid-template-rows: minmax\(0, 2fr\) minmax\(0, 1fr\)/,
    );

    expect(birthWizardCssSource).toMatch(/\.birth-activation-helix-arena[\s\S]*grid-row: 1/);

    expect(birthWizardCssSource).toMatch(/\.birth-activation-deck[\s\S]*grid-row: 2/);

    expect(birthWizardCssSource).toMatch(/\.birth-activation-deck[\s\S]*justify-self: center/);

    expect(birthWizardCssSource).toMatch(/\.birth-activation-screen--anchored[\s\S]*position: relative/);

    expect(birthWizardCssSource).toMatch(/\.birth-activation-screen--anchored[\s\S]*flex: 1/);

    expect(birthWizardCssSource).toMatch(/\.birth-activation-deck[\s\S]*width: min\(66\.666vw, 100%\)/);

    expect(birthWizardCssSource).toMatch(/\.birth-activation-deck[\s\S]*overflow-y: auto/);

    expect(birthWizardCssSource).toContain(".birth-activation-helix-arena::before");

    expect(birthWizardCssSource).toContain(".birth-activation-helix-slot::after");

    expect(birthWizardCssSource).toContain(".birth-activation-hud");

    expect(birthWizardCssSource).toContain(".birth-launch-particle");

    expect(birthWizardCssSource).toMatch(/\.birth-launch-btn[\s\S]*overflow: hidden/);

    expect(birthWizardCssSource).toMatch(/\.birth-launch-btn[\s\S]*contain: layout style/);

    expect(birthWizardCssSource).toMatch(/\.birth-activation-desc[\s\S]*white-space: nowrap/);

    expect(birthWizardCssSource).toMatch(/\.birth-activation-desc[\s\S]*var\(--lumina-cyan\)/);

    expect(birthWizardCssSource).toMatch(/\.birth-launch-btn__sublabel[\s\S]*text-align: center/);

    expect(birthCinematicLayoutSource).toContain("birth-activation-stack mx-auto");

    expect(birthCinematicLayoutSource).not.toContain("birth-activation-stack mx-auto flex");

    expect(birthCinematicLayoutSource).toContain("birth-activation-screen--anchored flex");

  });



  it("BirthActivateStep uses ceremony helix and T1 ambient shell", () => {

    expect(birthActivateSource).toContain("ceremonyMode");

    expect(birthActivateSource).toContain("birth-activation-hud");

    expect(birthActivateSource).toContain("birth-activation-helix-slot");

    expect(onboardingWizardSource).toContain("onboarding-shell--birth");

    expect(onboardingShellSource).toContain("onboarding-shell--birth");

    expect(onboardingShellSource).toContain("birth-activation-stars");

    expect(onboardingWizardSource).toContain("minimal={isBirthStep}");

    expect(birthGenesisDeckSource).toContain("birth-activation-progress");

    expect(onboardingWizardSource).toContain("onboarding-birth-column");

    expect(onboardingWizardSource).toContain("onboarding-birth-viewport");

    expect(onboardingWizardSource).toMatch(/isBirthStep[\s\S]*max-w-none/);

    expect(onboardingWizardSource).toMatch(/isBirthStep[\s\S]*flex-1/);

    expect(onboardingWizardSource).not.toMatch(/isBirthStep[\s\S]*h-full/);

    expect(onboardingWizardSource).not.toMatch(/isBirthStep[\s\S]*justify-end/);

    expect(birthActivateSource).toContain("min-h-0 w-full");

    expect(birthActivateSource).toContain("max-w-2xl");

  });



  it("birth wizard scroll container locks viewport without stable scrollbar gutter", () => {

    expect(onboardingWizardSource).toContain("isBirthStep");

    expect(onboardingWizardSource).toContain("overflow-hidden");

    expect(onboardingWizardSource).not.toMatch(/isBirthStep[\s\S]*justify-end/);

    expect(onboardingWizardSource).not.toContain("overflow-x-hidden overflow-y-auto overscroll-contain");

    expect(onboardingWizardSource).not.toContain("[scrollbar-gutter:stable]");

    expect(onboardingShellSource).toContain("h-dvh");

    expect(onboardingShellSource).toContain("onboarding-shell--form");

  });

  it("Lumina phase header is mounted on wizard, birth, and deck surfaces", () => {
    expect(luminaPhaseHeaderSource).toContain("lumina-phase-header__title");
    expect(luminaPhaseHeaderCssSource).toContain(".lumina-phase-header__eyebrow");
    expect(onboardingWizardSource).toContain("LuminaPhaseHeader");
    expect(onboardingWizardSource).toContain("resolveWizardPhaseHeader");
    expect(birthPhaseSource).toContain("LuminaPhaseHeader");
    expect(cockpitShellSource).toContain("resolveDeckPhaseHeader");
  });

});

