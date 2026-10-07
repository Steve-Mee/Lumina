import { describe, expect, it } from "vitest";

import { WIPE_CONFIRM_PHRASES, wipePhraseMatches } from "@/components/maturity/phaseWipeCopy";

describe("named wipe confirm phrases", () => {
  it("requires exact tokens matching the backend gate", () => {
    expect(WIPE_CONFIRM_PHRASES.awakening).toBe("WIPE AWAKENING");
    expect(WIPE_CONFIRM_PHRASES.birth).toBe("WIPE BIRTH");
    expect(WIPE_CONFIRM_PHRASES.full).toBe("WIPE FULL");
    expect(wipePhraseMatches("awakening", "WIPE AWAKENING")).toBe(true);
    expect(wipePhraseMatches("awakening", "  WIPE AWAKENING  ")).toBe(true);
    expect(wipePhraseMatches("awakening", "wipe awakening")).toBe(false);
    expect(wipePhraseMatches("awakening", "WIPE BIRTH")).toBe(false);
  });
});
