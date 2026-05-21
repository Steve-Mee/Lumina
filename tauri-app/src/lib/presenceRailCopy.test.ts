import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const railSource = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), "../components/cockpit/PresenceRail.tsx"),
  "utf8",
);

describe("presenceRailCopy", () => {
  it("does not show sync text in secondary slot", () => {
    expect(railSource).not.toContain("deckSyncNote");
    expect(railSource).not.toContain("syncNote");
  });

  it("does not render visible mode tagline span", () => {
    expect(railSource).not.toContain("presence-rail__tagline");
  });
});
