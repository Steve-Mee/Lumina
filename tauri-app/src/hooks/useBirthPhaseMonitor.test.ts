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
    expect(deckSource).toContain("sessionLocked");
    // Genesis presentation SSOT — one banner + CTA path inside the glass deck.
    expect(deckSource).toContain("resolveGenesisDeckPresentation");
    expect(deckSource).toContain("Start clean");
    expect(deckSource).toContain("RETRY BIRTH");
    expect(deckSource).toContain("birth-distress-callout");
  });
});
