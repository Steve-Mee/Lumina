import { describe, expect, it } from "vitest";

import { INTELLIGENCE_DECK_TAB_SUBTITLES } from "@/components/cockpit/IntelligenceDeckPanel";

describe("IntelligenceDeckPanel subtitles", () => {
  it("defines subtitles for all right deck tabs", () => {
    expect(INTELLIGENCE_DECK_TAB_SUBTITLES.brief).toContain("Decision");
    expect(INTELLIGENCE_DECK_TAB_SUBTITLES.adaptive).toContain("policy");
    expect(INTELLIGENCE_DECK_TAB_SUBTITLES.monitor).toContain("metrics");
    expect(INTELLIGENCE_DECK_TAB_SUBTITLES.performance).toContain("Equity");
    expect(INTELLIGENCE_DECK_TAB_SUBTITLES.realOps).toContain("REAL");
  });
});
