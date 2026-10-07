import { lazy, Suspense, type ReactNode } from "react";

import { BirthOrganismVisual } from "@/components/birth/BirthOrganismVisual";
import { StatusChip } from "@/components/birth/BirthGenesisDeckPrimitives";
import { BirthLaunchButton } from "@/components/birth/BirthLaunchButton";
import { HelpTip } from "@/components/ui/HelpTip";
import { cn } from "@/lib/utils";

const BirthHelixVisual = lazy(() =>
  import("@/components/birth/BirthHelixVisual").then((module) => ({
    default: module.BirthHelixVisual,
  })),
);

export type PhaseChip = {
  label: string;
  state: "ok" | "partial" | "warn" | "idle";
  tip: string;
};

function HelixFallback({ compact = false }: { compact?: boolean }) {
  return (
    <div className="flex h-full min-h-0 flex-1 items-center justify-center">
      <BirthOrganismVisual className={compact ? "size-16 opacity-80" : "size-48 opacity-80"} />
    </div>
  );
}

export function PhaseHelixStage({
  activating = false,
  variant = "genesis",
  trainingTrades,
}: {
  activating?: boolean;
  variant?: "genesis" | "mission";
  trainingTrades?: number;
}) {
  const helix = (
    <div className="helix-column-fill">
      <Suspense fallback={<HelixFallback compact={variant === "mission"} />}>
        <BirthHelixVisual
          ceremonyMode
          activating={activating}
          primed={activating}
          trainingTrades={trainingTrades}
          className="h-full min-h-0 w-full max-w-full"
        />
      </Suspense>
    </div>
  );

  if (variant === "mission") {
    return (
      <div className="birth-helix-accent-wrap helix-column-host pointer-events-none relative hidden min-h-0 w-full lg:flex">
        {helix}
      </div>
    );
  }

  return (
    <div
      className={cn(
        "birth-genesis-helix-stage birth-activation-helix-arena birth-helix-accent-wrap helix-column-host pointer-events-none min-h-0",
        activating && "birth-activation-helix-arena--charge",
      )}
    >
      <div className="birth-activation-stage-inner min-h-0 flex-1">
        <div className="birth-activation-helix-slot birth-helix-accent min-h-0 flex-1">{helix}</div>
      </div>
    </div>
  );
}

export function PhaseGenesisFrame({
  activating = false,
  trainingTrades,
  ariaLabel = "Phase charter",
  className,
  children,
}: {
  activating?: boolean;
  trainingTrades?: number;
  ariaLabel?: string;
  className?: string;
  children: ReactNode;
}) {
  return (
    <div
      className={cn(
        "living-phase-shell birth-mission-shell relative flex min-h-0 flex-1 flex-col overflow-hidden",
        className,
      )}
    >
      <div className="birth-genesis-grid min-h-0 flex-1 overflow-hidden p-3 md:p-4">
        <PhaseHelixStage activating={activating} variant="genesis" trainingTrades={trainingTrades} />
        <section
          className="birth-genesis-panel lumina-glass lumina-glass--overlay flex min-h-0 flex-col overflow-hidden"
          aria-label={ariaLabel}
        >
          {children}
        </section>
      </div>
    </div>
  );
}

export function PhaseMissionFrame({
  className,
  activating = false,
  trainingTrades,
  control,
  intel,
}: {
  className?: string;
  activating?: boolean;
  trainingTrades?: number;
  control: ReactNode;
  intel: ReactNode;
}) {
  return (
    <div
      className={cn(
        "living-phase-shell birth-mission-shell relative flex min-h-0 flex-1 flex-col overflow-hidden",
        className,
      )}
    >
      <div className="birth-mission-grid min-h-0 flex-1 overflow-hidden p-3 md:p-4">
        <PhaseHelixStage activating={activating} variant="mission" trainingTrades={trainingTrades} />
        {control}
        {intel}
      </div>
    </div>
  );
}

export function PhasePanelToolbar({
  title,
  subtitle,
  titleTip,
  trailing,
}: {
  title: string;
  subtitle?: string;
  titleTip?: string;
  trailing?: ReactNode;
}) {
  return (
    <header className="birth-mission-control__toolbar risk-envelope-panel__toolbar shrink-0">
      <div className="min-w-0">
        <div className="birth-genesis-title-row">
          <p className="birth-mission-control__toolbar-title risk-envelope-panel__toolbar-title">
            {title}
          </p>
          {titleTip ? <HelpTip text={titleTip} label={`${title} info`} /> : null}
        </div>
        {subtitle ? (
          <p
            className="mt-0.5 truncate font-mono text-[0.5rem] tracking-wide text-white/30 uppercase"
            title={subtitle}
          >
            {subtitle}
          </p>
        ) : null}
      </div>
      {trailing}
    </header>
  );
}

export function PhaseStatusStrip({
  chips,
  label,
}: {
  chips: PhaseChip[];
  label: string;
}) {
  return (
    <div
      className="birth-mission-status-strip risk-envelope-status-strip shrink-0"
      role="status"
      aria-label={label}
    >
      {chips.map((chip) => (
        <StatusChip key={chip.label} label={chip.label} state={chip.state} tip={chip.tip} />
      ))}
    </div>
  );
}

export function PhaseCtaBar({
  footnote,
  primaryLabel,
  onPrimary,
  primaryDisabled = false,
  primaryActivating = false,
  primaryActiveLabel,
  secondaryLabel,
  onSecondary,
  secondaryDisabled = false,
  links,
}: {
  footnote?: string;
  primaryLabel: string;
  onPrimary: () => void;
  primaryDisabled?: boolean;
  primaryActivating?: boolean;
  /** Shown while primaryActivating. Defaults must not claim a Birth start. */
  primaryActiveLabel?: string;
  secondaryLabel?: string;
  onSecondary?: () => void;
  secondaryDisabled?: boolean;
  links?: ReactNode;
}) {
  return (
    <div className="risk-envelope-cta-bar genesis-launch-cta phase-hub-cta shrink-0">
      {footnote ? (
        <p className="mb-1.5 text-center font-mono text-[0.5rem] tracking-[0.12em] text-white/30 uppercase">
          {footnote}
        </p>
      ) : null}
      <div className="phase-hub-cta__row">
        <BirthLaunchButton
          activating={primaryActivating}
          idleLabel={primaryLabel}
          activeLabel={primaryActiveLabel ?? primaryLabel}
          disabled={primaryDisabled}
          onClick={onPrimary}
          className="phase-hub-cta__primary"
        />
        {secondaryLabel && onSecondary ? (
          <button
            type="button"
            className="genesis-recovery-action-card__btn genesis-recovery-action-card__btn--idle phase-hub-cta__deck"
            disabled={secondaryDisabled}
            onClick={onSecondary}
          >
            {secondaryLabel}
          </button>
        ) : null}
      </div>
      {links ? <div className="mt-2 flex flex-wrap items-center justify-center gap-3">{links}</div> : null}
    </div>
  );
}

export function PhaseTextLink({
  label,
  onClick,
  disabled = false,
  danger = false,
}: {
  label: string;
  onClick: () => void;
  disabled?: boolean;
  danger?: boolean;
}) {
  return (
    <button
      type="button"
      className={cn(
        "font-mono text-[10px] tracking-wide underline-offset-2 hover:underline",
        danger ? "text-rose-200/70" : "text-cyan-200/80",
        disabled && "pointer-events-none opacity-50",
      )}
      disabled={disabled}
      onClick={onClick}
    >
      {label}
    </button>
  );
}
