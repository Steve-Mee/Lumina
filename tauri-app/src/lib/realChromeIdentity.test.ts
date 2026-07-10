import { readFileSync } from "node:fs";

import { dirname, join } from "node:path";

import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";



const commandHudSource = readFileSync(

  join(dirname(fileURLToPath(import.meta.url)), "../components/cockpit/CommandHud.tsx"),

  "utf8",

);

const modeSwitchSource = readFileSync(

  join(dirname(fileURLToPath(import.meta.url)), "../components/cockpit/ModeSwitch.tsx"),

  "utf8",

);

const stageSource = readFileSync(

  join(dirname(fileURLToPath(import.meta.url)), "../components/decision/DecisionTheaterStage.tsx"),

  "utf8",

);

const birthSource = readFileSync(

  join(dirname(fileURLToPath(import.meta.url)), "../components/birth/BirthPhaseScreen.tsx"),

  "utf8",

);

const nerveTapSource = readFileSync(

  join(dirname(fileURLToPath(import.meta.url)), "../components/cockpit/HudNerveTap.tsx"),

  "utf8",

);

const blockingOverlaySource = readFileSync(

  join(dirname(fileURLToPath(import.meta.url)), "../components/cockpit/DeckBlockingOverlay.tsx"),

  "utf8",

);

const communitySource = readFileSync(

  join(dirname(fileURLToPath(import.meta.url)), "../components/operations/CommunityPanel.tsx"),

  "utf8",

);

const historySource = readFileSync(

  join(

    dirname(fileURLToPath(import.meta.url)),

    "../components/intelligence/AdaptiveIntelligenceHistoryPanel.tsx",

  ),

  "utf8",

);



describe("REAL chrome identity", () => {

  it("does not use hardcoded cyan/emerald utility classes in key surfaces", () => {

    for (const source of [commandHudSource, stageSource, birthSource, nerveTapSource, communitySource, historySource]) {

      expect(source).not.toMatch(/border-cyan-4\d/);

      expect(source).not.toMatch(/bg-cyan-9\d/);

      expect(source).not.toMatch(/border-emerald-5\d/);

      expect(source).not.toMatch(/bg-emerald-6\d/);

    }

  });



  it("HudNerveTap uses CSS icon class instead of hardcoded cyan", () => {

    expect(nerveTapSource).toContain("hud-nerve-tap__icon");

    expect(nerveTapSource).not.toContain("text-cyan-200/90");

  });



  it("DeckBlockingOverlay uses mode presentation helpers not emerald welcome", () => {

    expect(blockingOverlaySource).toContain("welcomeOverlayPanelClass");

    expect(blockingOverlaySource).toContain("birthOverlayPanelClass");

    expect(blockingOverlaySource).not.toContain("border-emerald-500");

    expect(blockingOverlaySource).not.toContain("text-emerald-200");

  });



  it("uses mode presentation helpers in ModeSwitch", () => {

    expect(modeSwitchSource).toContain("modeSwitchShellClass");

    expect(modeSwitchSource).toContain("modeSwitchActivePillClass");

    expect(commandHudSource).toContain("ModeSwitch");

  });

});

