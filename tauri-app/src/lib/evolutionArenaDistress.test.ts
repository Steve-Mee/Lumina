import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const evolutionArenaSource = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), "../components/EvolutionArena.tsx"),
  "utf8",
);

describe("EvolutionArena distress grammar", () => {
  it("does not use flat amber utility boxes for error strip", () => {
    expect(evolutionArenaSource).not.toContain("border-amber-500/35 bg-amber-950/80");
    expect(evolutionArenaSource).toContain("distressPanelClass");
    expect(evolutionArenaSource).toContain("warnOverlayBodyClass");
  });

  it("sets data-mode on mount for REAL background path", () => {
    expect(evolutionArenaSource).toContain('data-mode={currentMode}');
    expect(evolutionArenaSource).toContain("evolution-arena-shell--real");
  });
});
