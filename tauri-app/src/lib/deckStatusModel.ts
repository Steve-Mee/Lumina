import type { ConnectionStatus } from "@/store/coreStore";

export type ModeSyncStatus = "idle" | "pending" | "error";

export type BlockingOverlayKind =
  | "backend"
  | "birth"
  | "fallback"
  | "welcome"
  | null;

export interface BlockingOverlayStates {
  backendDown: boolean;
  birthActive: boolean;
  fallbackActive: boolean;
  welcomeVisible: boolean;
}

const TRANSPORT_LABEL: Record<ConnectionStatus, string> = {
  connected: "Linked",
  connecting: "Connecting",
  reconnecting: "Reconnecting",
  disconnected: "Offline",
};

const TRANSPORT_DOT: Record<ConnectionStatus, string> = {
  connected: "bg-emerald-400/90 lumina-glow-edge",
  connecting: "bg-amber-400/90 animate-pulse",
  reconnecting: "bg-amber-400/90 animate-pulse",
  disconnected: "bg-red-400/80",
};

export function deckTransportLabel(
  connectionStatus: ConnectionStatus,
  fallbackMode: boolean,
): string {
  if (fallbackMode) {
    return "Polling";
  }
  return TRANSPORT_LABEL[connectionStatus];
}

export function deckTransportDotClass(
  connectionStatus: ConnectionStatus,
  fallbackMode: boolean,
): string {
  if (fallbackMode) {
    return "bg-amber-400/90 animate-pulse";
  }
  return TRANSPORT_DOT[connectionStatus];
}

export function deckSyncNote(
  syncStatus: ModeSyncStatus,
  error: string | null,
): string | null {
  if (syncStatus === "pending") {
    return "· syncing…";
  }
  if (syncStatus === "error") {
    return `· ${error ?? "sync failed"}`;
  }
  return null;
}

export function blockingOverlayPriority(
  states: BlockingOverlayStates,
): BlockingOverlayKind {
  if (states.backendDown) {
    return "backend";
  }
  if (states.birthActive) {
    return "birth";
  }
  if (states.fallbackActive) {
    return "fallback";
  }
  if (states.welcomeVisible) {
    return "welcome";
  }
  return null;
}
