import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

import { INTELLIGENCE_DECK_TAB_SUBTITLES } from "@/lib/intelligenceDeckNav";

const intelligenceDeckSource = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), "IntelligenceDeckPanel.tsx"),
  "utf8",
);

describe("IntelligenceDeckPanel subtitles", () => {
  it("defines subtitles for all right deck tabs", () => {
    expect(INTELLIGENCE_DECK_TAB_SUBTITLES.brief).toContain("Decision");
    expect(INTELLIGENCE_DECK_TAB_SUBTITLES.adaptive).toContain("policy");
    expect(INTELLIGENCE_DECK_TAB_SUBTITLES.monitor).toContain("metrics");
    expect(INTELLIGENCE_DECK_TAB_SUBTITLES.performance).toContain("Equity");
    expect(INTELLIGENCE_DECK_TAB_SUBTITLES.realOps).toContain("REAL");
  });
});

describe("IntelligenceDeckPanel REAL drawer contract", () => {
  it("does not auto-open subsystems drawer on REAL entry", () => {
    const useEffects = intelligenceDeckSource.match(/useEffect\([\s\S]*?\n  \},/g) ?? [];
    for (const effect of useEffects) {
      expect(effect).not.toContain("setDrawerOpen(true)");
    }
    expect(intelligenceDeckSource).toContain("realOpsHint");
    expect(intelligenceDeckSource).toContain("deck-tab-chip--hint-pulse");
  });
});