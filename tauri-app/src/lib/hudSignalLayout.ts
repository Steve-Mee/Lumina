import type { HudSignalGlow } from "@/components/cockpit/HudSignal";
import type { ConnectionStatus, TradingMode } from "@/store/coreStore";

export const HUD_SHOW_PNL_PREF_KEY = "lumina.hud.showPnlInSim";
export const HUD_HERO_PRIMARY_PREF_KEY = "lumina.hud.heroPrimary";
export const HUD_HERO_MAX = 2;

export type HudContextualKind = "regime" | "pnl" | "none";
export type HudHeroPrimary = "equity" | "fortress";

export interface HudSignalLayoutPrefs {
  showPnlInSim?: boolean;
  heroPrimary?: HudHeroPrimary;
}

/** @deprecated Use HudSignalLayoutPrefs */
export type HudLayoutPrefs = HudSignalLayoutPrefs;

export interface HudEquityConfig {
  kind: "equity";
  glow: HudSignalGlow;
  intensity: number;
}

export interface HudFortressConfig {
  kind: "fortress";
}

export interface HudContextualRegimeConfig {
  kind: "regime";
  glow: "violet";
  intensity: number;
  pulse: boolean;
}

export interface HudContextualPnlConfig {
  kind: "pnl";
  glow: HudSignalGlow;
}

export type HudContextualConfig = HudContextualRegimeConfig | HudContextualPnlConfig;

export interface HudSignalLayout {
  equity: HudEquityConfig;
  fortress: HudFortressConfig;
  contextual: HudContextualConfig | null;
  contextualKind: HudContextualKind;
}

export interface HudHeroLayout {
  primary: HudEquityConfig | HudFortressConfig;
  showContextualAnnexHint: boolean;
  contextualKind: HudContextualKind;
  heroPrimary: HudHeroPrimary;
}

export interface HudLayoutMetrics {
  regime: string;
  regimeConfidence: number | null;
  dailyPnlUsd: number | null;
}

export interface HudHeroContext {
  connectionStatus: ConnectionStatus;
  sessionActive: boolean;
  fallbackMode: boolean;
}

export function equityGlowForMode(mode: TradingMode): HudSignalGlow {
  return mode === "REAL" ? "gold" : "cyan";
}

export function pnlGlowForMode(mode: TradingMode, dailyPnlUsd: number | null): HudSignalGlow {
  if (dailyPnlUsd == null || dailyPnlUsd < 0) {
    return "warn";
  }
  return mode === "REAL" ? "gold" : "emerald";
}

export function resolveContextualKind(
  mode: TradingMode,
  prefs: HudSignalLayoutPrefs = {},
): HudContextualKind {
  if (mode === "REAL") {
    return "pnl";
  }
  return prefs.showPnlInSim ? "pnl" : "regime";
}

function buildContextual(
  mode: TradingMode,
  metrics: HudLayoutMetrics,
  prefs: HudSignalLayoutPrefs,
): HudContextualConfig | null {
  const contextualKind = resolveContextualKind(mode, prefs);
  const regimeLowConfidence =
    metrics.regimeConfidence !== null && metrics.regimeConfidence < 0.55;

  if (contextualKind === "regime") {
    return {
      kind: "regime",
      glow: "violet",
      intensity: regimeLowConfidence ? 0.45 : 0.85,
      pulse: regimeLowConfidence,
    };
  }
  if (contextualKind === "pnl") {
    return {
      kind: "pnl",
      glow: pnlGlowForMode(mode, metrics.dailyPnlUsd),
    };
  }
  return null;
}

export function resolveHudSignalLayout(
  mode: TradingMode,
  metrics: HudLayoutMetrics,
  equityIntensity: number,
  prefs: HudSignalLayoutPrefs = {},
): HudSignalLayout {
  const contextualKind = resolveContextualKind(mode, prefs);
  const contextual = buildContextual(mode, metrics, prefs);

  return {
    equity: {
      kind: "equity",
      glow: equityGlowForMode(mode),
      intensity: equityIntensity,
    },
    fortress: { kind: "fortress" },
    contextual,
    contextualKind,
  };
}

export function resolveHudHeroLayout(
  mode: TradingMode,
  metrics: HudLayoutMetrics,
  equityIntensity: number,
  prefs: HudSignalLayoutPrefs,
  context: HudHeroContext,
): HudHeroLayout {
  const heroPrimary = prefs.heroPrimary ?? "equity";
  const contextualKind = resolveContextualKind(mode, prefs);
  const contextual = buildContextual(mode, metrics, prefs);

  const primary: HudEquityConfig | HudFortressConfig =
    heroPrimary === "fortress"
      ? { kind: "fortress" }
      : {
          kind: "equity",
          glow: equityGlowForMode(mode),
          intensity: equityIntensity,
        };

  return {
    primary,
    showContextualAnnexHint: contextual !== null,
    contextualKind,
    heroPrimary,
  };
}

export function readHudLayoutPrefs(): HudSignalLayoutPrefs {
  try {
    const heroRaw = localStorage.getItem(HUD_HERO_PRIMARY_PREF_KEY);
    const heroPrimary: HudHeroPrimary | undefined =
      heroRaw === "fortress" ? "fortress" : heroRaw === "equity" ? "equity" : undefined;
    return {
      showPnlInSim: localStorage.getItem(HUD_SHOW_PNL_PREF_KEY) === "1",
      heroPrimary,
    };
  } catch {
    return {};
  }
}

export function writeHudLayoutPrefs(prefs: HudSignalLayoutPrefs): void {
  try {
    if (prefs.showPnlInSim) {
      localStorage.setItem(HUD_SHOW_PNL_PREF_KEY, "1");
    } else {
      localStorage.removeItem(HUD_SHOW_PNL_PREF_KEY);
    }
    if (prefs.heroPrimary) {
      localStorage.setItem(HUD_HERO_PRIMARY_PREF_KEY, prefs.heroPrimary);
    } else {
      localStorage.removeItem(HUD_HERO_PRIMARY_PREF_KEY);
    }
  } catch {
    // ignore storage failures
  }
}

export function resolveHudAnnexHintCopy(
  mode: TradingMode,
  kind: Exclude<HudContextualKind, "none">,
): string {
  if (mode === "REAL") {
    return kind === "pnl" ? "REAL P&L · annex" : "Guarded metrics · annex";
  }
  return kind === "pnl" ? "SIM P&L · annex" : "Regime · annex";
}
