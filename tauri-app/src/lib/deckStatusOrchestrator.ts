import type { BlockingOverlayKind } from "@/lib/deckStatusModel";

export type DeckStatusBannerKind = "recovery" | null;
export type DeckStatusRailChip = "recovery" | "sync" | "fallback" | null;

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
  banner: DeckStatusBannerKind;
  railChip: DeckStatusRailChip;
  suppressToast: boolean;
}

export function resolveDeckStatus(input: DeckStatusInput): DeckStatusResolution {
  const blocking = resolveBlockingKind(input);

  if (blocking !== null) {
    return {
      blocking,
      banner: null,
      railChip: null,
      suppressToast: true,
    };
  }

  if (input.backendRecovered) {
    return {
      blocking: null,
      banner: null,
      railChip: "recovery",
      suppressToast: true,
    };
  }

  if (input.syncPending) {
    return {
      blocking: null,
      banner: null,
      railChip: "sync",
      suppressToast: true,
    };
  }

  return {
    blocking: null,
    banner: null,
    railChip: null,
    suppressToast: false,
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

/** @deprecated Use resolveDeckStatus return value */
export type DeckStatusSurface = "none" | "chip" | "banner" | "blocking";

/** @deprecated Use resolveDeckStatus */
export function shouldShowStatusBanner(
  _resolution: { suppressBanner?: boolean },
  bannerKind: "backend" | "welcome" | null,
): boolean {
  return bannerKind !== null;
}
