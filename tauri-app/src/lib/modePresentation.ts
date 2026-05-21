import type { CSSProperties } from "react";

import type { Transition } from "framer-motion";

import { springLuxury, springSnappy } from "@/lib/motionPresets";
import { luminaSurfaceMutedClass } from "@/lib/glassGlowTaxonomy";
import type { TradingMode } from "@/store/coreStore";
import { cn } from "@/lib/utils";

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

export function modeSwitchShellClass(mode: TradingMode): string {
  return mode === "SIM"
    ? "border-cyan-400/30 bg-cyan-950/40"
    : "border-[color-mix(in_srgb,var(--real-chrome-accent)_28%,transparent)] bg-slate-900/50";
}

export function modeSwitchActivePillClass(mode: TradingMode, active: boolean): string {
  if (!active) {
    return "";
  }
  return mode === "SIM" ? "text-cyan-200" : "text-[#c9b896]";
}

export function modeSwitchActivePillMotionClass(mode: TradingMode): string {
  return mode === "SIM"
    ? "bg-[color-mix(in_srgb,var(--mode-sim-accent)_20%,transparent)] ring-1 ring-[color-mix(in_srgb,var(--mode-sim-accent)_40%,transparent)] lumina-glow-edge"
    : "bg-[color-mix(in_srgb,var(--real-chrome-accent)_18%,transparent)] ring-1 ring-[color-mix(in_srgb,var(--real-chrome-accent)_35%,transparent)]";
}

export function modeFinaleHeaderClass(mode: TradingMode): string {
  return mode === "SIM"
    ? "border-b border-[color-mix(in_srgb,var(--mode-sim-accent)_15%,transparent)] bg-[color-mix(in_srgb,var(--mode-sim-accent)_8%,transparent)]"
    : "border-b border-[color-mix(in_srgb,var(--real-chrome-accent)_15%,transparent)] bg-[color-mix(in_srgb,var(--real-chrome-accent)_8%,transparent)]";
}

export function modeSuccessIconClass(mode: TradingMode): string {
  return mode === "SIM" ? "text-cyan-300" : "text-[#c9b896]";
}

export function deckRecoveryChipClass(): string {
  return "inline-flex items-center gap-1 rounded-full border border-[color-mix(in_srgb,#34d399_30%,transparent)] px-2 py-0.5 text-[9px] tracking-wide text-[color-mix(in_srgb,#34d399_90%,white)] uppercase";
}

export function modeNodeBadgeClass(mode: TradingMode): string {
  return mode === "REAL"
    ? realBadgeClass()
    : "rounded bg-[color-mix(in_srgb,var(--mode-sim-accent)_15%,transparent)] px-1.5 py-0.5 text-[10px] tracking-wider uppercase text-[color-mix(in_srgb,var(--mode-sim-accent)_90%,white)]";
}

export function modeAccentBorderClass(mode: TradingMode): string {
  return mode === "SIM" ? "border-cyan-400/25" : "border-[color-mix(in_srgb,var(--real-chrome-accent)_25%,transparent)]";
}

export function modeApproveButtonClass(mode: TradingMode): string {
  return mode === "SIM"
    ? "border-emerald-500/35 bg-emerald-600/80 text-white hover:bg-emerald-600"
    : "border-[color-mix(in_srgb,var(--real-chrome-accent)_35%,transparent)] bg-[color-mix(in_srgb,var(--real-chrome-accent)_22%,transparent)] text-slate-100 hover:bg-[color-mix(in_srgb,var(--real-chrome-accent)_30%,transparent)]";
}

export function deckPanelFrameClass(
  frameVariant: "glass" | "muted",
  mode: TradingMode,
): string {
  if (frameVariant === "muted") {
    return cn("lumina-surface-muted rounded-lg py-0", modePanelClass(mode));
  }
  return cn(
    "lumina-glass lumina-glass--panel lumina-glass--interactive rounded-lg py-0",
    modePanelClass(mode),
  );
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

/** Full-screen blocking overlay scrim — canonical glass overlay grammar. */
export function deckOverlayScrimClass(variant: "blocking" | "safe" = "blocking"): string {
  const zIndex = variant === "safe" ? "z-[100]" : "z-[90]";
  return cn(
    "deck-overlay-scrim fixed inset-0 flex items-center justify-center p-6",
    zIndex,
    "lumina-glass lumina-glass--overlay",
  );
}

/** Birth progress blocking panel — SIM T1 tokens. */
export function birthOverlayPanelClass(): string {
  return cn(
    "w-full max-w-lg rounded-xl p-6 lumina-glass lumina-glass--overlay lumina-glow-halo",
    modeAccentBorderClass("SIM"),
  );
}

export function birthOverlayTitleClass(): string {
  return "font-mono text-sm tracking-[0.14em] text-cyan-200 uppercase";
}

export function birthOverlayProgressClass(): string {
  return "h-full bg-gradient-to-r from-cyan-400 to-violet-500 transition-all duration-700";
}

/** Welcome overlay — mode-aware, no emerald third accent. */
export function welcomeOverlayPanelClass(mode: TradingMode): string {
  return cn(
    "relative w-full max-w-lg rounded-xl p-6 lumina-glass lumina-glass--overlay lumina-glow-halo",
    modeAccentBorderClass(mode),
  );
}

export function welcomeOverlayTitleClass(mode: TradingMode): string {
  return mode === "SIM"
    ? "font-mono text-sm tracking-[0.14em] text-cyan-200 uppercase"
    : realOverlayTitleClass();
}

export function welcomeOverlayBodyClass(mode: TradingMode): string {
  return mode === "SIM"
    ? "text-sm leading-relaxed text-cyan-100/90"
    : realOverlayBodyClass();
}

export function welcomeOverlayIconClass(mode: TradingMode): string {
  return mode === "SIM" ? "text-cyan-300" : realOverlayIconClass();
}

export function welcomeOverlayDismissClass(mode: TradingMode): string {
  return mode === "SIM"
    ? "rounded p-1 text-cyan-200/80 hover:bg-cyan-900/40"
    : "rounded p-1 text-slate-300/80 hover:bg-slate-800/40";
}

export function welcomeOverlayStrongClass(mode: TradingMode): string {
  return mode === "SIM" ? "font-medium text-cyan-50" : "font-medium text-slate-100";
}

/** T3 utility surfaces — muted chrome with mode border. */
export function utilityPanelClass(mode: TradingMode): string {
  return cn("lumina-surface-muted rounded-lg p-3", modeAccentBorderClass(mode));
}

export function utilityListItemClass(mode: TradingMode): string {
  return cn(
    "rounded-md border px-3 py-2",
    modeAccentBorderClass(mode),
    "bg-[color-mix(in_srgb,var(--lumina-void)_28%,transparent)]",
  );
}

export function utilityInputClass(mode: TradingMode): string {
  return cn(
    "w-full rounded-md border py-2 font-mono text-xs text-foreground outline-none",
    "bg-[color-mix(in_srgb,var(--lumina-void)_35%,transparent)]",
    mode === "SIM"
      ? "border-white/10 focus:border-cyan-400/40"
      : "border-white/10 focus:border-[color-mix(in_srgb,var(--real-chrome-accent)_35%,transparent)]",
  );
}

export function utilityFieldInputClass(): string {
  return cn(
    "mt-1 w-full rounded border border-white/10 px-2 py-1 font-mono text-xs",
    "bg-[color-mix(in_srgb,var(--lumina-void)_40%,transparent)]",
  );
}

export function utilityCodeBlockClass(): string {
  return "mt-2 max-h-32 overflow-auto rounded-md lumina-surface-muted p-2 font-mono text-[9px] text-muted-foreground";
}

export function utilityMetricTileClass(mode: TradingMode): string {
  return cn("rounded border px-2 py-1.5 text-xs", modeAccentBorderClass(mode));
}

export function utilityQualityChipClass(mode: TradingMode, active: boolean): string {
  if (!active) {
    return cn("rounded-lg border px-3 py-2.5 text-left transition-colors", luminaSurfaceMutedClass("border border-white/10 hover:border-white/20"));
  }
  return mode === "SIM"
    ? "rounded-lg border border-cyan-400/40 bg-cyan-500/10 px-3 py-2.5 text-left transition-colors"
    : "rounded-lg border border-[color-mix(in_srgb,var(--real-chrome-accent)_35%,transparent)] bg-[color-mix(in_srgb,var(--real-chrome-accent)_12%,transparent)] px-3 py-2.5 text-left transition-colors";
}

export function panelLoaderScrimClass(inset: "full" | "inset" = "full"): string {
  return cn(
    "panel-loader-scrim absolute z-10 flex items-center justify-center",
    inset === "full" ? "inset-0" : "inset-2 rounded-lg",
  );
}
