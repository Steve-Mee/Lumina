import { cn } from "@/lib/utils";

export const LUMINA_GLASS_CLASS = "lumina-glass";

export type LuminaGlowLevel = "edge" | "halo" | "ambient";

const GLOW_CLASS: Record<LuminaGlowLevel, string> = {
  edge: "lumina-glow-edge",
  halo: "lumina-glow-halo",
  ambient: "lumina-glow-ambient",
};

/** Official glow level class (max 3: edge / halo / ambient). */
export function luminaGlowClass(level: LuminaGlowLevel): string {
  return GLOW_CLASS[level];
}

/** Glass surface without ad-hoc bg-black layers. */
export function glassSurfaceClass(...extra: Array<string | false | null | undefined>): string {
  return cn(LUMINA_GLASS_CLASS, ...extra);
}

/** Interactive glass panel (hover edge-accent glow). */
export function glassInteractiveClass(...extra: Array<string | false | null | undefined>): string {
  return cn(LUMINA_GLASS_CLASS, "lumina-glass--interactive", ...extra);
}

/** Muted annex/ops surface — no blur, no glow. */
export function luminaSurfaceMutedClass(...extra: Array<string | false | null | undefined>): string {
  return cn("lumina-surface-muted", ...extra);
}

export type LuminaInteractiveVariant = "default" | "danger" | "ghost";

const INTERACTIVE_VARIANT_CLASS: Record<LuminaInteractiveVariant, string> = {
  default: "lumina-interactive",
  danger: "lumina-interactive lumina-interactive--danger",
  ghost: "lumina-interactive lumina-interactive--ghost",
};

/** Clickable control affordance — Lumina cursor + hover glow. */
export function luminaInteractiveClass(
  variant: LuminaInteractiveVariant = "default",
  ...extra: Array<string | false | null | undefined>
): string {
  return cn(INTERACTIVE_VARIANT_CLASS[variant], ...extra);
}

/** Panel surfaces must not combine ambient glow with glass. */
export function assertPanelGlowLevel(level: LuminaGlowLevel): LuminaGlowLevel {
  if (level === "ambient") {
    throw new Error("ambient glow is shell-only; use edge or halo on panels");
  }
  return level;
}
