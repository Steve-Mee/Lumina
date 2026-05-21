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



const birthDiagnosticsSource = readFileSync(

  join(dirname(fileURLToPath(import.meta.url)), "../components/birth/BirthDiagnosticsDrawer.tsx"),

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



describe("onboarding surface contracts", () => {

  it("Birth finale keeps telemetry in diagnostics drawer not T1 viewport", () => {

    expect(birthPhaseSource).toContain("Birth complete");

    expect(birthPhaseSource).toContain("Enter command deck");

    expect(birthPhaseSource).not.toContain("CheckCircle2");

    expect(birthPhaseSource).not.toContain("birth-finale-hero");

    expect(birthPhaseSource).toContain("defaultOpen={awakening}");

  });



  it("BirthPhaseScreen HUD is floating copy without glass overlay", () => {

    const heroBlock =

      birthPhaseSource.split("birth-phase-hero")[1]?.split("showRecovery")[0] ?? "";

    expect(heroBlock).toContain("birth-phase-hud");

    expect(heroBlock).not.toContain("lumina-glass--overlay");

    expect(heroBlock).not.toContain("Settings2");

  });



  it("BirthPhaseScreen keeps T3 diagnostics content out of hero viewport", () => {

    expect(birthPhaseSource).toContain("birth-phase-ops");

    expect(birthPhaseSource).toContain("BirthDiagnosticsDrawer");

    const heroBlock =

      birthPhaseSource.split("birth-phase-hero")[1]?.split("showRecovery")[0] ?? "";

    expect(heroBlock).not.toContain("BirthMetricsStrip");

    expect(heroBlock).not.toContain("BirthMilestoneTrack");

    expect(heroBlock).toContain("BirthPhasePulse");

  });



  it("Birth running uses full-viewport height without min-h-screen overflow", () => {

    expect(birthPhaseSource).toContain("h-dvh");

    expect(birthPhaseSource).not.toContain("min-h-screen");

    expect(birthPhaseSource).toContain("overflow-hidden");

    expect(birthPhaseSource).toContain("birth-phase-helix-stage");

  });



  it("BirthDiagnosticsDrawer portals overlay to document body", () => {

    expect(birthDiagnosticsSource).toContain("createPortal");

    expect(birthDiagnosticsSource).toContain("document.body");

    expect(birthDiagnosticsSource).toContain("backdrop-blur-md");

  });



  it("Birth running ops zone has no persistent stop control", () => {

    expect(birthPhaseSource).not.toMatch(/birth-phase-ops[\s\S]*Stop birth phase/);

    expect(birthDiagnosticsSource).toContain("Stop birth phase");

    expect(birthDiagnosticsSource).toContain("Activity");

    expect(birthDiagnosticsSource).toContain("Telemetry");

  });



  it("BirthActivateStep default deck shows one slider outside collapsed genesis panel", () => {

    expect(birthActivateSource).toContain("Genesis parameters");

    expect(birthActivateSource).toContain("genesisOpen");

    const defaultDeck = birthActivateSource.split("{genesisOpen ?")[0] ?? "";

    const sliderCount = (defaultDeck.match(/<BirthHoloSlider/g) ?? []).length;

    expect(sliderCount).toBe(1);

  });



  it("OnboardingShell omits deck vignette on birth screen", () => {

    expect(onboardingShellSource).toContain("birth-phase-screen");

    expect(onboardingShellSource).toContain("hideDeckVignette");

  });



  it("CommandHud exposes Save & Start when engine is off", () => {

    expect(commandHudSource).toContain("saveAndStart");

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

    expect(birthActivateSource).toContain("birth-activation-progress");

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

});

