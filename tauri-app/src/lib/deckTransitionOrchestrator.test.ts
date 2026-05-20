import { describe, expect, it } from "vitest";

import {
  DECK_TRANSITION_DURATION,
  resolveTransitionDuration,
} from "@/lib/deckTransitionOrchestrator";

describe("deckTransitionOrchestrator", () => {
  it("panelTab transition duration is 0.35s", () => {
    expect(DECK_TRANSITION_DURATION.panelTab).toBe(0.35);
    expect(resolveTransitionDuration("panelTab")).toBe(0.35);
  });
});
