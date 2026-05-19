import { describe, expect, it } from "vitest";

import { isCommandDeckBlocked } from "@/lib/commandDeckGuard";
import type { CoreStore } from "@/store/coreStore";

function state(
  operatorMode: CoreStore["operatorMode"],
  safeModeActive: boolean,
): CoreStore {
  return {
    operatorMode,
    safeModeActive,
  } as CoreStore;
}

describe("isCommandDeckBlocked", () => {
  it("blocks only when REAL and safe mode active", () => {
    expect(isCommandDeckBlocked(state("REAL", true))).toBe(true);
    expect(isCommandDeckBlocked(state("REAL", false))).toBe(false);
    expect(isCommandDeckBlocked(state("SIM", true))).toBe(false);
    expect(isCommandDeckBlocked(state("SIM", false))).toBe(false);
  });
});
