import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

import { deckSyncNote } from "@/lib/deckStatusModel";

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

  it("renders deckSyncNote in secondary desktop slot when sync pending", () => {
    expect(presenceRailSource).toContain("deckSyncNote");
    const note = deckSyncNote("pending", null);
    expect(note).toBeTruthy();
    expect(presenceRailSource).toContain("syncNote");
  });

  it("uses unified secondary channel on all breakpoints", () => {
    expect(presenceRailSource).not.toContain("lg:hidden");
    expect(presenceRailSource).toContain("presence-rail__velocity");
  });

  it("uses pulseLanguage presence dot classes", () => {
    expect(presenceRailSource).toContain("presenceDotClass");
  });
});
