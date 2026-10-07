import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");

const birthSource = readFileSync(join(root, "components/birth/BirthHelixVisual.tsx"), "utf8");
const ceremonySource = readFileSync(
  join(root, "components/birth/BirthHelixCeremonyScene.tsx"),
  "utf8",
);
const scenesSource = readFileSync(join(root, "components/birth/BirthHelixScenes.tsx"), "utf8");
const coreSource = readFileSync(join(root, "components/LivingCore.tsx"), "utf8");
const evolutionSceneSource = readFileSync(
  join(root, "components/evolution/EvolutionForceGraphScene.tsx"),
  "utf8",
);
const evolutionCameraSource = readFileSync(
  join(root, "components/evolution/EvolutionArenaCamera.tsx"),
  "utf8",
);
const primitivesSource = readFileSync(join(root, "components/three/helixPrimitives.tsx"), "utf8");
const organismCameraSource = readFileSync(
  join(root, "components/organism/OrganismStageCamera.tsx"),
  "utf8",
);
const organismSceneSource = readFileSync(
  join(root, "components/birth/BirthHelixScenes.tsx"),
  "utf8",
);

describe("three scene identity", () => {
  it("BirthHelix and LivingCore do not import each other's scene files", () => {
    expect(birthSource).not.toContain("LivingCoreScene");
    expect(birthSource).not.toContain('from "@/components/LivingCore"');
    expect(coreSource).not.toContain("BirthHelixScene");
    expect(coreSource).not.toContain('from "@/components/birth/BirthHelixVisual"');
  });

  it("shared primitives live in helixPrimitives module", () => {
    expect(primitivesSource).toContain("useLerpedColor");
    expect(primitivesSource).toContain("createStrandGradientMaterial");
    expect(birthSource).toContain("helixPrimitives");
  });

  it("Birth helix uses quality tiers and ceremony DoubleHelixStrands", () => {
    expect(birthSource).toContain("helixTubeSegments");
    expect(birthSource).toContain("BirthHelixScene");
    expect(scenesSource).toContain("CeremonyHelixScene");
    expect(scenesSource).toContain("OrganismAnatomy");
    expect(ceremonySource).toContain("DoubleHelixStrands");
    // Gradient strand materials live in shared primitives; ceremony composes DoubleHelixStrands.
    expect(primitivesSource).toContain("createStrandGradientMaterial");
    expect(ceremonySource).not.toMatch(/meshStandardMaterial[\s\S]*emissive/);
  });

  it("Birth ceremony scene avoids DNA rung cylinders", () => {
    expect(ceremonySource).toContain("DoubleHelixStrands");
    expect(ceremonySource).not.toContain("cylinderGeometry");
  });

  it("Living Core uses dedicated halo animation class", () => {
    expect(coreSource).toContain("livingCoreHaloAnimationClass");
    expect(coreSource).not.toContain("immersiveHaloClass");
  });

  it("organism stage camera centers the being in its column", () => {
    expect(organismCameraSource).toContain("lookAt(0, 0, 0)");
    expect(organismCameraSource).toContain("organismFitDistance");
    expect(organismCameraSource).toContain("helix-column-host");
    expect(organismCameraSource).toContain("setSize");
    expect(organismSceneSource).toContain("CeremonyHelixScene");
    expect(organismSceneSource).toContain("OrganismAnatomy");
    expect(organismSceneSource).toContain("OrganismStageCamera");
    expect(organismSceneSource).not.toContain("maturationClient");
  });

  it("Evolution arena locks camera and disables zoom by default", () => {
    expect(evolutionCameraSource).toContain("enableZoom={false}");
    expect(evolutionSceneSource).not.toContain("EvolutionNodeTooltip");
    expect(evolutionCameraSource).toContain("enableRotate={false}");
    expect(evolutionCameraSource).toContain("arenaCameraDistance");
    expect(evolutionSceneSource).toContain("championBirth");
  });
});
