import type { TradingMode } from "@/store/coreStore";

export function modeMotionScale(mode: TradingMode): number {
  return mode === "SIM" ? 1 : 0.45;
}

export function modePanelClass(mode: TradingMode): string {
  return mode === "SIM" ? "mode-panel-sim" : "mode-panel-real";
}

export function citadelCoreGradient(mode: TradingMode): string {
  return mode === "SIM"
    ? "from-cyan-950/80 via-black/60 to-violet-950/70"
    : "from-slate-900/90 via-black/70 to-amber-950/40";
}

export function citadelShieldClass(mode: TradingMode): string {
  return mode === "SIM" ? "text-cyan-300/80" : "text-amber-300/70";
}
