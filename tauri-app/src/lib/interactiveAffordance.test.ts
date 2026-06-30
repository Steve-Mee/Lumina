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

describe("interactiveAffordance", () => {
  it("defines Lumina cursor and hover tokens", () => {
    expect(indexCssSource).toContain("--lumina-cursor-interactive");
    expect(indexCssSource).toContain("--lumina-hover-glow");
    expect(indexCssSource).toContain("/cursors/lumina-pointer.svg");
  });

  it("defines lumina-interactive hover and cursor rules", () => {
    expect(cockpitCssSource).toContain(".lumina-interactive");
    expect(cockpitCssSource).toMatch(/\.lumina-interactive[\s\S]*cursor:\s*var\(--lumina-cursor-interactive\)/);
    expect(cockpitCssSource).toContain(".lumina-interactive--danger");
    expect(cockpitCssSource).toContain(".lumina-interactive--ghost");
    expect(cockpitCssSource).toContain("@media (hover: hover)");
  });

  it("applies interactive cursor defaults on Button", () => {
    expect(buttonSource).toContain("lumina-interactive");
    expect(buttonSource).toContain("cursor-[var(--lumina-cursor-interactive)]");
    expect(buttonSource).toContain("disabled:cursor-not-allowed");
  });

  it("composes interactive variant classes via helper", () => {
    expect(luminaInteractiveClass("danger")).toContain("lumina-interactive--danger");
    expect(luminaInteractiveClass("ghost")).toContain("lumina-interactive--ghost");
  });
});
