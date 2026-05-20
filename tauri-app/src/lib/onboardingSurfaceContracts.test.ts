import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const birthPhaseSource = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), "../components/birth/BirthPhaseScreen.tsx"),
  "utf8",
);

const backendStepSource = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), "../components/onboarding/steps/BackendStep.tsx"),
  "utf8",
);

describe("onboarding surface contracts", () => {
  it("BirthPhaseScreen HUD uses lumina-glass--hud tier", () => {
    expect(birthPhaseSource).toContain("lumina-glass--hud");
  });

  it("onboarding steps use luminaSurfaceMutedClass instead of flat bg-black/20", () => {
    expect(backendStepSource).toContain("luminaSurfaceMutedClass");
    expect(backendStepSource).not.toContain("bg-black/20");
  });
});
