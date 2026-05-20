import type { RightDeckTab } from "@/store/deckPanelStore";
import type { TradingMode } from "@/store/coreStore";

export const INTELLIGENCE_PRIMARY_TABS = ["brief", "performance"] as const;
export type IntelligencePrimaryTab = (typeof INTELLIGENCE_PRIMARY_TABS)[number];

export const INTELLIGENCE_DECK_TAB_SUBTITLES: Record<RightDeckTab, string> = {
  brief: "Decision theater & reasoning chain",
  adaptive: "Live policy stack & transition history",
  performance: "Equity curve, P&L & session KPIs",
  realOps: "REAL capital preservation & exposure",
  evolutionApprovals: "Open challenger proposals",
  liveActivity: "Engine status & log tail",
  monitor: "Health, twin, shadow & training metrics",
  community: "Trader league & global wisdom",
  hardware: "Hardware tier & model management",
  admin: "Maintenance & first-boot reset",
};

export const OPS_TAB_LABELS: Partial<Record<RightDeckTab, string>> = {
  monitor: "Monitor",
  liveActivity: "Activity",
  adaptive: "Adaptive",
  evolutionApprovals: "Approvals",
  realOps: "REAL Ops",
  community: "Community",
  hardware: "Hardware",
  admin: "Admin",
};

export interface OpsSection {
  id: string;
  label: string;
  tabs: RightDeckTab[];
  mode?: TradingMode;
}

export const INTELLIGENCE_OPS_SECTIONS: OpsSection[] = [
  { id: "system", label: "System", tabs: ["monitor", "liveActivity"] },
  { id: "evolution", label: "Evolution", tabs: ["adaptive", "evolutionApprovals"] },
  { id: "real", label: "Capital", tabs: ["realOps"], mode: "REAL" },
  { id: "platform", label: "Platform", tabs: ["community", "hardware", "admin"] },
];

const OPS_TAB_SET = new Set<RightDeckTab>(
  INTELLIGENCE_OPS_SECTIONS.flatMap((section) => section.tabs),
);

export function isOpsTab(tab: RightDeckTab): boolean {
  return OPS_TAB_SET.has(tab);
}

export function opsTabLabel(tab: RightDeckTab): string {
  return OPS_TAB_LABELS[tab] ?? tab;
}

export function resolveOpsSections(mode: TradingMode): OpsSection[] {
  return INTELLIGENCE_OPS_SECTIONS.filter(
    (section) => section.mode === undefined || section.mode === mode,
  );
}

export function primaryTabLabel(tab: IntelligencePrimaryTab): string {
  return tab === "brief" ? "Brief" : "Performance";
}
