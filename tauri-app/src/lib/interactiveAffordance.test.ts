import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

import { luminaInteractiveClass } from "@/lib/glassGlowTaxonomy";

const indexCssSource = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), "../index.css"),
  "utf8",
);

const cockpitCssSource = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), "../styles/cockpit.css"),
  "utf8",
);

const buttonSource = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), "../components/ui/button.tsx"),
  "utf8",
);

const styleSheets = [
  "styles/cockpit.css",
  "styles/onboarding.css",
  "styles/birthPhase.css",
  "styles/birthWizard.css",
].map((rel) =>
  readFileSync(join(dirname(fileURLToPath(import.meta.url)), `../${rel}`), "utf8"),
);

describe("interactiveAffordance", () => {
  it("defines Lumina cursor tokens as OS-native pointer contract (no custom reticle)", () => {
    expect(indexCssSource).toContain("--lumina-cursor-interactive");
    expect(indexCssSource).toContain("--lumina-cursor-default");
    expect(indexCssSource).toContain("--lumina-cursor-disabled");
    expect(indexCssSource).toContain("--lumina-hover-glow");
    // Single interactive cursor: system pointer — no mixed SVG reticle.
    expect(indexCssSource).toMatch(
      /--lumina-cursor-interactive:\s*pointer\s*;/,
    );
    expect(indexCssSource).not.toContain("/cursors/lumina-pointer.svg");
  });

  it("applies global interactive cursor to native controls", () => {
    expect(indexCssSource).toMatch(
      /button:not\(:disabled\):not\(\[aria-disabled="true"\]\)[\s\S]*cursor:\s*var\(--lumina-cursor-interactive\)/,
    );
    expect(indexCssSource).toContain(".cursor-pointer");
    expect(indexCssSource).toContain("cursor: var(--lumina-cursor-interactive)");
    // Unlayered safety net (beats preflight) + onboarding orphan buttons
    expect(indexCssSource).toContain("Unlayered interactive cursor safety net");
  });

  it("defines lumina-interactive hover and cursor rules", () => {
    expect(cockpitCssSource).toContain(".lumina-interactive");
    expect(cockpitCssSource).toMatch(
      /\.lumina-interactive[\s\S]*cursor:\s*var\(--lumina-cursor-interactive\)/,
    );
    expect(cockpitCssSource).toContain(".lumina-interactive--danger");
    expect(cockpitCssSource).toContain(".lumina-interactive--ghost");
    expect(cockpitCssSource).toContain("@media (hover: hover)");
  });

  it("applies interactive cursor defaults on Button", () => {
    expect(buttonSource).toContain("lumina-interactive");
    expect(buttonSource).toContain("cursor-[var(--lumina-cursor-interactive)]");
    expect(buttonSource).toContain("disabled:cursor-[var(--lumina-cursor-disabled)]");
  });

  it("does not leave raw cursor: pointer in core style sheets (use tokens)", () => {
    for (const css of styleSheets) {
      expect(css).not.toMatch(/cursor:\s*pointer\s*;/);
    }
  });

  it("composes interactive variant classes via helper", () => {
    expect(luminaInteractiveClass("danger")).toContain("lumina-interactive--danger");
    expect(luminaInteractiveClass("ghost")).toContain("lumina-interactive--ghost");
  });
});
