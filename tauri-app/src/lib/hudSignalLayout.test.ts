import { describe, expect, it } from "vitest";

import {
  equityGlowForMode,
  HUD_HERO_MAX,
  pnlGlowForMode,
  resolveContextualKind,
  resolveHudHeroLayout,
  resolveHudSignalLayout,
} from "@/lib/hudSignalLayout";

describe("hudSignalLayout", () => {
  const metrics = {
    regime: "trend",
    regimeConfidence: 0.8,
    dailyPnlUsd: 120,
  };

  it("REAL shows equity gold glow and P&L contextual", () => {
    const layout = resolveHudSignalLayout("REAL", metrics, 0.9);
    expect(layout.equity.glow).toBe("gold");
    expect(layout.contextualKind).toBe("pnl");
    expect(layout.contextual?.kind).toBe("pnl");
    expect(pnlGlowForMode("REAL", 120)).toBe("gold");
  });

  it("SIM defaults to regime contextual unless pref toggled", () => {
    const layout = resolveHudSignalLayout("SIM", metrics, 0.9);
    expect(equityGlowForMode("SIM")).toBe("cyan");
    expect(resolveContextualKind("SIM")).toBe("regime");
    expect(layout.contextual?.kind).toBe("regime");

    const withPnl = resolveHudSignalLayout("SIM", metrics, 0.9, { showPnlInSim: true });
    expect(withPnl.contextualKind).toBe("pnl");
    expect(withPnl.contextual?.kind).toBe("pnl");
  });

  it("negative P&L uses warn glow in both modes", () => {
    expect(pnlGlowForMode("REAL", -50)).toBe("warn");
    expect(pnlGlowForMode("SIM", -50)).toBe("warn");
  });

  it("resolveHudHeroLayout caps at HUD_HERO_MAX slots", () => {
    expect(HUD_HERO_MAX).toBe(2);

    const idle = resolveHudHeroLayout("SIM", metrics, 0.9, {}, {
      connectionStatus: "disconnected",
      sessionActive: false,
      fallbackMode: false,
    });
    expect(idle.primary.kind).toBe("equity");
    expect(idle.secondary).toBeNull();
    expect(idle.showContextualAnnexHint).toBe(true);

    const live = resolveHudHeroLayout("SIM", metrics, 0.9, {}, {
      connectionStatus: "connected",
      sessionActive: true,
      fallbackMode: false,
    });
    expect(live.secondary?.kind).toBe("regime");
    expect(live.showContextualAnnexHint).toBe(false);

    const fortress = resolveHudHeroLayout("REAL", metrics, 0.9, { heroPrimary: "fortress" }, {
      connectionStatus: "connected",
      sessionActive: true,
      fallbackMode: false,
    });
    expect(fortress.primary.kind).toBe("fortress");
    expect(fortress.secondary?.kind).toBe("pnl");
  });
});
