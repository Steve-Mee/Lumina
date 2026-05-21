import type { TradingMode } from "@/store/coreStore";

export function presenceDotClass(mode: TradingMode, engineCompanion: boolean): string {
  const base =
    mode === "SIM" ? "presence-rail__live-dot--sim" : "presence-rail__live-dot--real";
  return engineCompanion ? `${base} presence-rail__live-dot--engine` : base;
}

export function livingCoreHaloAnimationClass(mode: TradingMode): string {
  return mode === "SIM" ? "living-core-halo--pulse" : "living-core-halo--breathe-slow";
}
