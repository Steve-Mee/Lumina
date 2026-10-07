import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const appSource = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), "../App.tsx"),
  "utf8",
);
const cockpitShellSource = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), "../components/cockpit/CockpitShell.tsx"),
  "utf8",
);
const commandDeckScreenSource = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), "../components/cockpit/CommandDeckScreen.tsx"),
  "utf8",
);
const statusBarSource = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), "../components/cockpit/StatusBar.tsx"),
  "utf8",
);
const intelligenceSource = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), "../components/cockpit/IntelligenceDeckPanel.tsx"),
  "utf8",
);
const evolutionSource = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), "../components/cockpit/EvolutionDeckPanel.tsx"),
  "utf8",
);
const realSafeSource = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), "../components/cockpit/RealSafeModeOverlay.tsx"),
  "utf8",
);
const blockingSource = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), "../components/cockpit/DeckBlockingOverlay.tsx"),
  "utf8",
);
const coreSlotSource = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), "../components/cockpit/CorePanelSlot.tsx"),
  "utf8",
);
const cockpitCss = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), "../styles/cockpit.css"),
  "utf8",
);

describe("glass stack budget", () => {
  it("default cockpit viewport does not mount StatusBar", () => {
    expect(cockpitShellSource).not.toContain("StatusBar");
    expect(cockpitShellSource).not.toContain("CommandHud");
    expect(cockpitShellSource).toContain('variant="compact"');
    expect(commandDeckScreenSource).toContain("CommandHud");
    expect(statusBarSource).toContain("lumina-glass--hud");
    expect(statusBarSource).toContain("status-bar--glass");
  });

  it("Command Deck uses genesis helix + one overlay ops panel", () => {
    expect(appSource).toContain("CommandDeckScreen");
    expect(commandDeckScreenSource).toContain("command-deck-ops");
    expect(commandDeckScreenSource).toContain("PhaseHelixStage");
    expect(commandDeckScreenSource).toContain("lumina-glass--overlay");
    expect(commandDeckScreenSource).toContain("command-deck-ops__chrome");
    expect(commandDeckScreenSource).toContain('frameVariant="muted"');
    expect(cockpitCss).toContain(".command-deck-ops__hud > .command-hud");
    expect(cockpitCss).toContain("min-height: 0 !important");
    expect(cockpitCss).toContain(".command-deck-ops__board .lumina-surface-muted");
  });

  it("Command Deck locks to one dvh viewport without page scroll", () => {
    expect(cockpitShellSource).toContain("h-dvh");
    expect(cockpitShellSource).toContain("max-h-dvh");
    expect(cockpitShellSource).toContain("overflow-hidden");
    expect(cockpitCss).toContain("html:has(.cockpit-shell--phase)");
    expect(cockpitCss).toContain(".cockpit-shell__stage");
    expect(cockpitCss).toContain("minmax(0, 1fr)");
  });

  it("Intelligence deck defaults to glass frame", () => {
    expect(intelligenceSource).toContain('frameVariant = "glass"');
    expect(intelligenceSource).toContain("deckPanelFrameClass");
  });

  it("Evolution deck defaults to muted frame", () => {
    expect(evolutionSource).toContain('frameVariant = "muted"');
  });

  it("blocking overlays use canonical lumina-glass--overlay scrim", () => {
    expect(blockingSource).toContain("deckOverlayScrimClass");
    expect(realSafeSource).toContain("deckOverlayScrimClass");
    expect(blockingSource).not.toContain("backdrop-blur-md");
    expect(realSafeSource).not.toContain("backdrop-blur-md");
    expect(cockpitCss).toContain(".deck-overlay-scrim");
  });

  it("CorePanelSlot loaders use panel-loader-scrim not raw bg-black", () => {
    expect(coreSlotSource).toContain("panelLoaderScrimClass");
    expect(coreSlotSource).not.toContain("bg-black/40");
  });

  it("Living Core uses the shared phase helix stage", () => {
    expect(commandDeckScreenSource).toContain("PhaseHelixStage");
    expect(commandDeckScreenSource).toContain('variant="mission"');
    expect(coreSlotSource).toContain("living-core-frame--immersive");
  });

  it("REAL mode mutes ambient grid and mesh layers", () => {
    expect(cockpitCss).toContain('.cockpit-shell[data-mode="REAL"] .cockpit-grid');
    expect(cockpitCss).toMatch(
      /\.cockpit-shell\[data-mode="REAL"\] \.cockpit-grid[\s\S]*opacity:\s*0\.08/,
    );
    expect(cockpitCss).toMatch(
      /\.cockpit-shell\[data-mode="REAL"\]::before[\s\S]*opacity:\s*0\.06/,
    );
  });

  it("HUD organism center demotes shell halo when visible", () => {
    expect(cockpitCss).toContain(".cockpit-shell:has(.hud-organism-center)::after");
  });
});
