import type { CSSProperties } from "react";

import type { Transition } from "framer-motion";

import { springLuxury, springSnappy } from "@/lib/motionPresets";
import type { TradingMode } from "@/store/coreStore";

export function modeMotionScale(mode: TradingMode): number {
  return mode === "SIM" ? 1 : 0.45;
}

export function modePanelClass(mode: TradingMode): string {
  return mode === "SIM" ? "mode-panel-sim" : "mode-panel-real";
}

export function modeAccentCssVars(mode: TradingMode): CSSProperties {
  if (mode === "SIM") {
    return {
      "--deck-accent": "var(--mode-sim-accent)",
      "--deck-glow": "color-mix(in srgb, var(--mode-sim-accent) 22%, transparent)",
      "--deck-border": "color-mix(in srgb, var(--mode-sim-accent) 16%, transparent)",
    } as CSSProperties;
  }
  return {
    "--deck-accent": "var(--mode-real-accent)",
    "--deck-glow": "color-mix(in srgb, var(--mode-real-muted) 18%, transparent)",
    "--deck-border": "color-mix(in srgb, var(--mode-real-muted) 20%, transparent)",
  } as CSSProperties;
}

/** Tier-2 panel/dialog title accent. */
export function modeTitleClass(mode: TradingMode): string {
  return mode === "SIM" ? "text-cyan-200/90" : "text-slate-200/90";
}

/** Tier-2 uppercase micro-label accent. */
export function modeLabelClass(mode: TradingMode): string {
  return mode === "SIM" ? "text-cyan-300/80" : "text-slate-400/80";
}

/** Tier-2 secondary value / velocity accent. */
export function modeValueClass(mode: TradingMode): string {
  return mode === "SIM" ? "text-cyan-300/90" : "text-[#c9b896]/80";
}

/** Shared Tier-2 semantic class for CSS shell overrides. */
export function modeTextTier2Class(mode: TradingMode, muted = false): string {
  if (muted) {
    return "mode-text-tier2-muted";
  }
  return mode === "SIM" ? "mode-text-tier2 mode-text-tier2-sim" : "mode-text-tier2";
}

export function citadelFieldEnvelopeScale(mode: TradingMode): number {
  return mode === "SIM" ? 1.12 : 1;
}

export function modeSpring(mode: TradingMode, luxury = false) {
  const base = luxury ? springLuxury : springSnappy;
  const scale = modeMotionScale(mode);
  if (scale >= 1) {
    return base;
  }
  return {
    ...base,
    stiffness: Math.round(base.stiffness * scale),
    damping: Math.round(base.damping * (0.85 + scale * 0.15)),
  };
}

export function modeTransition(
  mode: TradingMode,
  reducedMotion: boolean,
  luxury = false,
): Transition | undefined {
  if (reducedMotion) {
    return { duration: 0 };
  }
  return modeSpring(mode, luxury);
}

export function citadelCoreGradient(mode: TradingMode): string {
  return mode === "SIM"
    ? "from-cyan-950/80 via-black/60 to-violet-950/70"
    : "from-slate-900/90 via-black/70 to-slate-800/50";
}

export function citadelShieldClass(mode: TradingMode): string {
  return mode === "SIM" ? "text-cyan-300/80" : "text-slate-300/75";
}

/** Tailwind fallback for command-primary outside .cockpit-shell scope. */
export function commandPrimaryClass(mode: TradingMode): string {
  return mode === "SIM"
    ? "border-cyan-400/35 bg-cyan-500/20 text-cyan-100"
    : "border-slate-500/30 bg-slate-800/35 text-slate-100";
}

/** Tailwind fallback for command-ghost outside .cockpit-shell scope. */
export function commandGhostClass(mode: TradingMode): string {
  return mode === "SIM"
    ? "border-white/10 text-cyan-200/90 hover:text-cyan-100"
    : "border-white/10 text-slate-300/90 hover:text-[#c9b896]/90";
}

/** @deprecated Use realOverlayPanelClass */
export function realOverlayClass(): string {
  return realOverlayPanelClass();
}

/** @deprecated Use warnOverlayPanelClass */
export function warnOverlayClass(): string {
  return warnOverlayPanelClass();
}

/** REAL protective overlay — slate glass + soft gold accent (not alarm amber). */
export function realOverlayPanelClass(): string {
  return "border-slate-500/35 lumina-glass lumina-glass--overlay lumina-glow-halo";
}

export function realOverlayTitleClass(): string {
  return "font-mono text-sm tracking-[0.14em] text-slate-200 uppercase";
}

export function realOverlayBodyClass(): string {
  return "text-sm leading-relaxed text-slate-200/85";
}

export function realOverlayMetaClass(): string {
  return "font-mono text-[10px] text-slate-300/75";
}

export function realOverlayIconClass(): string {
  return "text-[#c9b896]";
}

export function realDialogTitleClass(): string {
  return "text-slate-200";
}

export function realDialogBodyClass(): string {
  return "text-slate-300/90";
}

export function realBadgeClass(): string {
  return "border-slate-500/40 bg-slate-800/40 text-[#c9b896] lumina-glow-edge";
}

/** Pending approval / highlight accent — gold in REAL, amber in SIM. */
export function pendingHighlightClass(mode: TradingMode): string {
  return mode === "REAL" ? "text-[#c9b896]/90" : "text-amber-200/90";
}

export type DrawerBadgeVariant = "warn" | "mode";

export function drawerBadgeClass(variant: DrawerBadgeVariant, mode: TradingMode): string {
  if (variant === "mode" && mode === "REAL") {
    return "bg-[color-mix(in_srgb,var(--real-chrome-accent)_88%,transparent)] text-slate-950";
  }
  return "bg-amber-500/90 text-black";
}

export function modeSwitchTooltip(mode: TradingMode): string {
  return mode === "REAL" ? "Capital Protection" : "Hyper Evolution";
}

/** Warning/degraded telemetry overlays — amber reserved for true alerts. */
export function warnOverlayPanelClass(): string {
  return "border-[color-mix(in_srgb,var(--status-warn)_35%,transparent)] lumina-glass lumina-glass--overlay lumina-glow-halo";
}

export type DistressVariant = "warn" | "error";

/** Canonical distress panel — glass overlay + variant border. */
export function distressPanelClass(variant: DistressVariant = "warn"): string {
  if (variant === "error") {
    return "border-[color-mix(in_srgb,#ef4444_35%,transparent)] lumina-glass lumina-glass--overlay lumina-glow-halo";
  }
  return warnOverlayPanelClass();
}

export function reasoningSpineTitleClass(mode: TradingMode): string {
  return mode === "REAL" ? "text-[#c9b896]/90" : "text-cyan-200/90";
}

export function warnOverlayTitleClass(): string {
  return "font-mono text-sm tracking-[0.14em] text-[color-mix(in_srgb,var(--status-warn-fg)_90%,white)] uppercase";
}

export function warnOverlayBodyClass(): string {
  return "text-sm leading-relaxed text-[color-mix(in_srgb,var(--status-warn-fg)_85%,transparent)]";
}

export function warnOverlayIconClass(): string {
  return "text-[var(--status-warn-icon)]";
}
