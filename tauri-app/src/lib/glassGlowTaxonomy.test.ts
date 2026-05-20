import { describe, expect, it } from "vitest";

import {
  assertPanelGlowLevel,
  glassInteractiveClass,
  glassSurfaceClass,
  luminaGlowClass,
  luminaSurfaceMutedClass,
} from "@/lib/glassGlowTaxonomy";

describe("glassGlowTaxonomy", () => {
  it("maps glow levels to official CSS classes", () => {
    expect(luminaGlowClass("edge")).toBe("lumina-glow-edge");
    expect(luminaGlowClass("halo")).toBe("lumina-glow-halo");
    expect(luminaGlowClass("ambient")).toBe("lumina-glow-ambient");
  });

  it("builds glass surface without duplicate bg utilities", () => {
    expect(glassSurfaceClass("rounded-lg")).toBe("lumina-glass rounded-lg");
    expect(glassInteractiveClass("rounded-lg")).toBe(
      "lumina-glass lumina-glass--interactive rounded-lg",
    );
  });

  it("builds muted annex surface class", () => {
    expect(luminaSurfaceMutedClass("p-3")).toBe("lumina-surface-muted p-3");
  });

  it("rejects ambient glow on panels", () => {
    expect(assertPanelGlowLevel("edge")).toBe("edge");
    expect(assertPanelGlowLevel("halo")).toBe("halo");
    expect(() => assertPanelGlowLevel("ambient")).toThrow(/shell-only/);
  });
});
