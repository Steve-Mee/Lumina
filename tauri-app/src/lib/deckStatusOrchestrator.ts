import type { BlockingOverlayKind } from "@/lib/deckStatusModel";

export type DeckStatusRailChip = "recovery" | "fallback" | null;

export interface DeckStatusInput {
  backendDown: boolean;
  birthActive: boolean;
  fallbackActive: boolean;
  welcomeVisible: boolean;
  backendRecovered: boolean;
  syncPending: boolean;
  syncError: boolean;
}

export interface DeckStatusResolution {
  blocking: BlockingOverlayKind;
  railChip: DeckStatusRailChip;
  suppressToast: boolean;
}

export function resolveDeckStatus(input: DeckStatusInput): DeckStatusResolution {
  const blocking = resolveBlockingKind(input);

  if (blocking !== null) {
    return {
      blocking,
      railChip: null,
      suppressToast: true,
    };
  }

  if (input.backendRecovered) {
    return {
      blocking: null,
      railChip: "recovery",
      suppressToast: true,
    };
  }

  return {
    blocking: null,
    railChip: null,
    suppressToast: input.syncPending,
  };
}

function resolveBlockingKind(input: DeckStatusInput): BlockingOverlayKind {
  if (input.backendDown) {
    return "backend";
  }
  if (input.birthActive) {
    return "birth";
  }
  if (input.fallbackActive) {
    return "fallback";
  }
  if (input.welcomeVisible) {
    return "welcome";
  }
  return null;
}
