import type { LuminaPhasePresentation, LuminaPhaseTone } from "@/lib/luminaPhasePresentation";
import { cn } from "@/lib/utils";

export type LuminaPhaseHeaderVariant = "hero" | "strip" | "compact";

export interface LuminaPhaseHeaderProps extends LuminaPhasePresentation {
  variant?: LuminaPhaseHeaderVariant;
  className?: string;
}

export function LuminaPhaseHeader({
  eyebrow,
  title,
  status,
  tone = "cyan",
  variant = "strip",
  className,
}: LuminaPhaseHeaderProps) {
  return (
    <header
      className={cn(
        "lumina-phase-header lumina-glass lumina-glass--panel pointer-events-none relative shrink-0 border-b border-white/10 text-center",
        toneClass(tone),
        variantClass(variant),
        className,
      )}
      aria-label={`${eyebrow}: ${title}`}
    >
      <div className="lumina-phase-header__accent deck-panel-accent absolute inset-x-0 top-0 h-px origin-center" />
      <div className="lumina-phase-header__glow" aria-hidden />
      <div className="lumina-phase-header__inner relative z-[1]">
        <p className="lumina-phase-header__eyebrow">{eyebrow}</p>
        <h1 className="lumina-phase-header__title">{title}</h1>
        {status ? <p className="lumina-phase-header__status">{status}</p> : null}
      </div>
      <div className="lumina-phase-header__rule" aria-hidden />
    </header>
  );
}

function toneClass(tone: LuminaPhaseTone): string {
  return `lumina-phase-header--${tone}`;
}

function variantClass(variant: LuminaPhaseHeaderVariant): string {
  return `lumina-phase-header--${variant}`;
}
