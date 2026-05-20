import type { CenterDeckTab } from "@/store/deckPanelStore";

export const EVOLUTION_DECK_TAB_SUBTITLES: Record<CenterDeckTab, string> = {
  evolution: "Pending mutation proposals",
  ppo: "Live policy evolution & training analytics",
  readiness: "SIM stability & REAL readiness criteria",
};

export const EVOLUTION_PRIMARY_TABS = ["evolution"] as const;
export type EvolutionPrimaryTab = (typeof EVOLUTION_PRIMARY_TABS)[number];

export const EVOLUTION_OPS_TABS = ["ppo", "readiness"] as const;
export type EvolutionOpsTab = (typeof EVOLUTION_OPS_TABS)[number];

export interface EvolutionOpsSection {
  id: string;
  label: string;
  tabs: CenterDeckTab[];
}

export const EVOLUTION_OPS_SECTIONS: EvolutionOpsSection[] = [
  { id: "analytics", label: "Analytics", tabs: ["ppo", "readiness"] },
];

const OPS_TAB_SET = new Set<CenterDeckTab>(EVOLUTION_OPS_SECTIONS.flatMap((s) => s.tabs));

export function isEvolutionOpsTab(tab: CenterDeckTab): boolean {
  return OPS_TAB_SET.has(tab);
}

export function evolutionOpsTabLabel(tab: CenterDeckTab): string {
  if (tab === "ppo") return "PPO Evolution";
  if (tab === "readiness") return "SIM Readiness";
  return tab;
}

export function primaryEvolutionTabLabel(tab: EvolutionPrimaryTab): string {
  return tab === "evolution" ? "Evolution Queue" : tab;
}
