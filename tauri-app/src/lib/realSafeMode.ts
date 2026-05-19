import type { ConnectionStatus, TradingMode } from "@/store/coreStore";

export const REAL_SAFE_MODE_THRESHOLD_MS = 15_000;

export function shouldArmSafeModeTimer(
  operatorMode: TradingMode,
  connectionStatus: ConnectionStatus,
): boolean {
  return operatorMode === "REAL" && connectionStatus !== "connected";
}

export function shouldShowSafeModeOverlay(
  operatorMode: TradingMode,
  safeModeActive: boolean,
): boolean {
  return operatorMode === "REAL" && safeModeActive;
}
