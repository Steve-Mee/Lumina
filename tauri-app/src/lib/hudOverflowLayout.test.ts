import { describe, expect, it } from "vitest";

import {
  HUD_OVERFLOW_MAX_ITEMS,
  resolveOverflowItems,
} from "@/lib/hudOverflowLayout";

describe("hudOverflowLayout", () => {
  it("caps overflow at five items", () => {
    const items = resolveOverflowItems({
      mode: "SIM",
      runtime: { alive: true, message: "ok" },
      apiKeyConfigured: true,
    });
    expect(items.length).toBeLessThanOrEqual(HUD_OVERFLOW_MAX_ITEMS);
    expect(items.length).toBe(5);
  });

  it("includes save and start only when engine is off and key is configured", () => {
    const off = resolveOverflowItems({
      mode: "SIM",
      runtime: { alive: false, message: "idle" },
      apiKeyConfigured: true,
    });
    expect(off.some((item) => item.id === "saveAndStart")).toBe(true);
    expect(off.some((item) => item.id === "stopEngine")).toBe(false);

    const on = resolveOverflowItems({
      mode: "SIM",
      runtime: { alive: true, message: "ok" },
      apiKeyConfigured: true,
    });
    expect(on.some((item) => item.id === "saveAndStart")).toBe(false);
    expect(on.some((item) => item.id === "stopEngine")).toBe(true);
  });

  it("always includes safety, bot config, and launch ninja within cap", () => {
    const items = resolveOverflowItems({
      mode: "REAL",
      runtime: null,
      apiKeyConfigured: false,
    });
    const ids = items.map((item) => item.id);
    expect(ids).toContain("safety");
    expect(ids).toContain("botConfig");
    expect(ids).toContain("launchNinja");
    expect(items.length).toBeLessThanOrEqual(HUD_OVERFLOW_MAX_ITEMS);
  });
});
