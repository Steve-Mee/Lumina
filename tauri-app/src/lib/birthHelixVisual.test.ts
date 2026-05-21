import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const birthHelixSource = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), "../components/birth/BirthHelixVisual.tsx"),
  "utf8",
);

describe("BirthHelixVisual motion contract", () => {
  it("uses VisibilityCanvas and ceremony-aware CSS fallback", () => {
    expect(birthHelixSource).toContain("VisibilityCanvas");
    expect(birthHelixSource).toContain("ceremonyMode");
    expect(birthHelixSource).toContain("BirthOrganismVisual");
  });

  it("passes reducedMotion into the helix scene", () => {
    expect(birthHelixSource).toContain("reducedMotion={prefersReducedMotion}");
    expect(birthHelixSource).not.toContain("reducedMotion={false}");
  });
});
