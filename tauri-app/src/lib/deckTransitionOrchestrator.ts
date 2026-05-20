import type { TradingMode } from "@/store/coreStore";

export type DeckTransitionKind = "modeSwitch" | "birthEntry" | "panelTab" | "none";

export interface DeckTransitionRequest {
  kind: DeckTransitionKind;
  targetMode?: TradingMode;
  durationSec?: number;
  scopeSelector?: string;
}

export interface DeckTransitionState {
  active: boolean;
  kind: DeckTransitionKind;
  targetMode: TradingMode | null;
  durationSec: number;
  scopeSelector: string;
}

export const DECK_TRANSITION_DURATION = {
  modeSwitchReal: 1.0,
  modeSwitchSim: 0.8,
  birthEntry: 0.9,
  panelTab: 0.35,
} as const;

export function resolveTransitionDuration(
  kind: DeckTransitionKind,
  targetMode?: TradingMode,
): number {
  switch (kind) {
    case "modeSwitch":
      return targetMode === "REAL"
        ? DECK_TRANSITION_DURATION.modeSwitchReal
        : DECK_TRANSITION_DURATION.modeSwitchSim;
    case "birthEntry":
      return DECK_TRANSITION_DURATION.birthEntry;
    case "panelTab":
      return DECK_TRANSITION_DURATION.panelTab;
    default:
      return DECK_TRANSITION_DURATION.modeSwitchSim;
  }
}

export function createTransitionState(
  request: DeckTransitionRequest,
): DeckTransitionState {
  const durationSec =
    request.durationSec ?? resolveTransitionDuration(request.kind, request.targetMode);
  return {
    active: request.kind !== "none",
    kind: request.kind,
    targetMode: request.targetMode ?? null,
    durationSec,
    scopeSelector: request.scopeSelector ?? ".cockpit-shell",
  };
}

export const IDLE_TRANSITION: DeckTransitionState = {
  active: false,
  kind: "none",
  targetMode: null,
  durationSec: 0,
  scopeSelector: ".cockpit-shell",
};
