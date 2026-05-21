import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const presenceRailSource = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), "PresenceRail.tsx"),
  "utf8",
);

describe("PresenceRail layout contract", () => {
  it("does not render a visible tagline span in the rail", () => {
    expect(presenceRailSource).not.toMatch(/>\s*\{tagline\}\s*</);
    expect(presenceRailSource).toContain("title={tagline}");
  });

  it("limits readable text zones to primary live label and secondary metrics", () => {
    expect(presenceRailSource).toContain("presence-rail__live");
    expect(presenceRailSource).toContain("presence-rail__velocity");
  });

  it("does not render sync copy in the rail secondary slot", () => {
    expect(presenceRailSource).not.toContain("deckSyncNote");
    expect(presenceRailSource).not.toContain("syncNote");
  });

  it("uses unified secondary channel on all breakpoints", () => {
    expect(presenceRailSource).not.toContain("lg:hidden");
    expect(presenceRailSource).toContain("presence-rail__velocity");
  });

  it("uses pulseLanguage presence dot classes without orphaned animation class", () => {
    expect(presenceRailSource).toContain("presenceDotClass");
    expect(presenceRailSource).not.toContain("presenceDotAnimationClass");
  });

  it("styles mode icon via CSS hook not inline Tailwind mode colors", () => {
    expect(presenceRailSource).toContain("presence-rail__mode-icon");
    expect(presenceRailSource).not.toContain("border-cyan-400/15");
  });
});
