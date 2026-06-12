import { describe, expect, it } from "vitest";

import { resolveDeckBirthGate } from "@/lib/deckBirthGate";

describe("deckBirthGate", () => {
  it("returns none when artifacts are ok", () => {
    expect(
      resolveDeckBirthGate({
        status: "completed",
        artifacts_ok: true,
      }),
    ).toBe("none");
  });

  it("returns running for active birth without artifacts", () => {
    expect(
      resolveDeckBirthGate({
        status: "running",
        artifacts_ok: false,
      }),
    ).toBe("running");
  });

  it("returns incomplete for interrupted and error without artifacts", () => {
    expect(
      resolveDeckBirthGate({
        status: "interrupted",
        artifacts_ok: false,
      }),
    ).toBe("incomplete");

    expect(
      resolveDeckBirthGate({
        status: "error",
        artifacts_ok: false,
      }),
    ).toBe("incomplete");
  });

  it("returns incomplete for completed status without artifacts", () => {
    expect(
      resolveDeckBirthGate({
        status: "completed",
        artifacts_ok: false,
        progress: { progress_pct: 100 },
      }),
    ).toBe("incomplete");
  });

  it("returns incomplete for idle without artifacts (fail-closed)", () => {
    expect(
      resolveDeckBirthGate({
        status: "idle",
        artifacts_ok: false,
      }),
    ).toBe("incomplete");
  });
});
