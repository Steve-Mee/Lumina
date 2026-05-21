import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const appSource = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), "../App.tsx"),
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
  it("StatusBar uses hud glass tint without panel glass", () => {
    expect(statusBarSource).toContain("lumina-glass--hud");
    expect(statusBarSource).toContain("status-bar--glass");
    expect(statusBarSource).not.toContain("lumina-glass--panel");
    expect(statusBarSource).not.toContain("toLocaleTimeString");
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

  it("Living Core uses frameless immersive slot", () => {
    expect(appSource).toContain("frameless");
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
