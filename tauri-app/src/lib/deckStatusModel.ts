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
  mode: "SIM" | "REAL" = "SIM",
): string {
  if (fallbackMode) {
    return mode === "REAL"
      ? "bg-amber-400/80 animate-pulse"
      : "bg-amber-400/90 animate-pulse";
  }
  const tinted = {
    connected:
      mode === "REAL"
        ? "bg-[color-mix(in_srgb,var(--mode-real-accent)_85%,#34d399_15%)] lumina-glow-edge"
        : "bg-emerald-400/90 lumina-glow-edge",
    connecting: "bg-amber-400/90 animate-pulse",
    reconnecting: "bg-amber-400/90 animate-pulse",
    disconnected: "bg-red-400/80",
  } as const;
  return tinted[connectionStatus];
}
