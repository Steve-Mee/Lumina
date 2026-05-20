import type { HudSignalGlow } from "@/components/cockpit/HudSignal";
import type { LiveTradingSnapshot } from "@/lib/liveTradingTypes";
import type { RiskLevel, TradingMode } from "@/store/coreStore";

export function formatKellyLabel(mode: TradingMode, fraction: number): string {
  const pct = `${Math.round(fraction * 100)}%`;
  return mode === "REAL" ? `${pct} · Quarter-Kelly` : `${pct} · SIM cap`;
}

export function riskHudGlow(riskLevel: RiskLevel): HudSignalGlow {
  switch (riskLevel) {
    case "NORMAL":
    case "ELEVATED":
      return "emerald";
    case "HIGH":
      return "amber";
    case "CRITICAL":
    case "UNKNOWN":
      return "amber";
    default:
      return "neutral";
  }
}

export function hasDebugPayload(trading: LiveTradingSnapshot | null): boolean {
  if (!trading) {
    return false;
  }
  return trading.current_dream != null || trading.runtime_state != null;
}

export function formatPositionSide(trading: LiveTradingSnapshot | null): string {
  const position = trading?.position;
  const qty = position?.live_qty ?? 0;
  if (qty > 0) {
    return "LONG";
  }
  if (qty < 0) {
    return "SHORT";
  }
  return position?.side_signal?.toUpperCase() || "FLAT";
}

export function formatPositionQty(trading: LiveTradingSnapshot | null): string {
  const qty = trading?.position?.live_qty ?? 0;
  if (qty === 0) {
    return "Flat";
  }
  return `${Math.abs(qty)} ct`;
}

export function signalChipClass(signal: string): string {
  const normalized = signal.toUpperCase();
  if (normalized === "BUY" || normalized === "LONG") {
    return "decision-signal-buy";
  }
  if (normalized === "SELL" || normalized === "SHORT") {
    return "decision-signal-sell";
  }
  return "decision-signal-hold";
}

export function verdictToneClass(tone: "high" | "moderate" | "low"): string {
  switch (tone) {
    case "high":
      return "border-emerald-400/30 bg-emerald-500/10 text-emerald-300";
    case "moderate":
      return "border-amber-400/30 bg-amber-500/10 text-amber-300";
    case "low":
      return "border-red-400/30 bg-red-500/10 text-red-300";
  }
}
