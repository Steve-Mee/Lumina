import type { CSSProperties } from "react";

import type { CenterDeckTab, RightDeckTab } from "@/store/deckPanelStore";
import type { TradingMode } from "@/store/coreStore";
export const ANALYTICS_CENTER_TABS = ["ppo", "readiness"] as const;
export type AnalyticsCenterTab = (typeof ANALYTICS_CENTER_TABS)[number];

export const ANALYTICS_RIGHT_TABS = [
  "performance",
  "monitor",
  "liveActivity",
  "adaptive",
  "evolutionApprovals",
  "realOps",
  "community",
  "hardware",
  "admin",
] as const;
export type AnalyticsRightTab = (typeof ANALYTICS_RIGHT_TABS)[number];

const ANALYTICS_CENTER_SET = new Set<CenterDeckTab>(ANALYTICS_CENTER_TABS);
const ANALYTICS_RIGHT_SET = new Set<RightDeckTab>(ANALYTICS_RIGHT_TABS);

export function isAnalyticsCenterTab(tab: CenterDeckTab): boolean {
  return ANALYTICS_CENTER_SET.has(tab);
}

export function isAnalyticsRightTab(tab: RightDeckTab): boolean {
  return ANALYTICS_RIGHT_SET.has(tab);
}

export function analyticsAnnexClass(): "analytics-annex" {
  return "analytics-annex";
}

export function analyticsAnnexCssVars(mode: TradingMode = "SIM"): CSSProperties {
  if (mode === "REAL") {
    return {
      "--annex-fg": "oklch(0.72 0.04 55)",
      "--annex-muted": "oklch(0.58 0.02 260 / 75%)",
      "--annex-border": "oklch(1 0 0 / 5%)",
      "--annex-bg": "oklch(0.11 0.008 260 / 0.92)",
      "--annex-surface": "oklch(0 0 0 / 20%)",
    } as CSSProperties;
  }
  return {
    "--annex-fg": "oklch(0.72 0.02 260)",
    "--annex-muted": "oklch(0.58 0.015 260 / 75%)",
    "--annex-border": "oklch(1 0 0 / 5%)",
    "--annex-bg": "oklch(0.11 0.008 260 / 0.92)",
    "--annex-surface": "oklch(0 0 0 / 20%)",
  } as CSSProperties;
}

export function analyticsAnnexTabClass(): "analytics-annex-tab" {
  return "analytics-annex-tab";
}
