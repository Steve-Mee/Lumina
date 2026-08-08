import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

const monitorSource = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), "./useBirthPhaseMonitor.ts"),
  "utf8",
);

const deckSource = readFileSync(
  join(
    dirname(fileURLToPath(import.meta.url)),
    "../components/birth/BirthGenesisDeck.tsx",
  ),
  "utf8",
);

describe("useBirthPhaseMonitor cold session probe", () => {
  it("retries status aggressively after full app restart", () => {
    expect(monitorSource).toContain("COLD_PROBE_ATTEMPTS");
    expect(monitorSource).toContain("COLD_PROBE_GAP_MS");
    expect(monitorSource).toContain("markSessionProbeError");
    expect(monitorSource).toContain("sessionHydrated");
  });

  it("locks Activate and surfaces loading recovery until session is known", () => {
    expect(deckSource).toContain("sessionProbePending");
    expect(deckSource).toContain("Loading session state");
    expect(deckSource).toContain("Activate stays locked");
    expect(deckSource).toContain("Loading Resume · Wipe birth data · Full wipe");
    expect(deckSource).toContain("sessionLocked");
    expect(deckSource).toContain("disabled={busy || sessionLocked}");
  });
});
