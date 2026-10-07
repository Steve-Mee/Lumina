import { describe, expect, it } from "vitest";

import { barBookChip } from "@/components/cockpit/CommandDeckStatusStrip";

describe("barBookChip", () => {
  it("names an unmeasured book as unknown", () => {
    expect(barBookChip(null)).toEqual({
      label: "BARS",
      state: "idle",
      tip: "Barboek nog niet gemeten.",
    });
  });

  it("locks when NT entries are closed", () => {
    expect(
      barBookChip({
        complete: false,
        lock_new_entries: true,
        reason: "unexplained",
        missing_count: 3,
        message: "3 missing NT 1m bars",
      }),
    ).toEqual({
      label: "BARS LOCK",
      state: "warn",
      tip: "Nieuwe entries dicht. 3 missing NT 1m bars",
    });
  });

  it("shows OK only when the book is complete and open", () => {
    expect(
      barBookChip({
        complete: true,
        lock_new_entries: false,
        reason: "",
        missing_count: 0,
        message: "",
      }),
    ).toEqual({
      label: "BARS OK",
      state: "ok",
      tip: "NT 1m-barboek is volledig. Nieuwe entries open.",
    });
  });

  it("does not paint OK on an incomplete open book", () => {
    const chip = barBookChip({
      complete: false,
      lock_new_entries: false,
      reason: "filling",
      missing_count: 1,
      message: "",
    });
    expect(chip.label).toBe("BARS");
    expect(chip.state).toBe("partial");
    expect(chip.tip).toContain("filling");
  });
});
