import type { ReactNode } from "react";
import { useRef } from "react";

import { OrganismEnvelopeProvider } from "@/context/OrganismEnvelopeContext";
import { LuminaLogo } from "@/components/cockpit/LuminaLogo";
import { useOrganismShellVars } from "@/hooks/useOrganismShellVars";
import { usePrefersReducedMotion } from "@/hooks/usePrefersReducedMotion";
import { selectVisualQuality, useVisualSettingsStore } from "@/store/visualSettingsStore";
import { cn } from "@/lib/utils";

interface OnboardingShellProps {
  children: ReactNode;
  className?: string;
}

export function OnboardingShell({ children, className }: OnboardingShellProps) {
  const shellRef = useRef<HTMLDivElement>(null);
  const reducedMotion = usePrefersReducedMotion();
  const visualQuality = useVisualSettingsStore(selectVisualQuality);
  const clockFrozen = visualQuality === "low";
  const hideDeckVignette = className?.includes("birth-phase-screen");
  const formOnlyAmbient = className?.includes("onboarding-shell--form");
  const birthAmbient = className?.includes("onboarding-shell--birth");
  useOrganismShellVars(shellRef, "SIM", reducedMotion, clockFrozen);

  return (
    <OrganismEnvelopeProvider>
      <div
        ref={shellRef}
        data-mode="SIM"
        className={cn(
          "onboarding-shell cockpit-shell lumina-glow-ambient relative flex flex-col overflow-hidden text-foreground",
          formOnlyAmbient ? "h-dvh max-h-dvh min-h-0" : "h-full min-h-full",
          className,
        )}
      >
        {birthAmbient ? (
          <div className="birth-activation-stars cockpit-stars pointer-events-none absolute inset-0" />
        ) : formOnlyAmbient ? null : (
          <>
            <div className="cockpit-stars pointer-events-none absolute inset-0 opacity-50" />
            <div className="cockpit-grid pointer-events-none absolute inset-0 opacity-30" />
          </>
        )}
        {hideDeckVignette ? null : (
          <div className="deck-vignette pointer-events-none" aria-hidden />
        )}
        <div className="relative z-10 flex min-h-0 flex-1 flex-col">{children}</div>
      </div>
    </OrganismEnvelopeProvider>
  );
}

export function OnboardingBrand() {
  return (
    <div className="flex flex-col items-center gap-4 text-center">
      <LuminaLogo className="size-28 md:size-32" />
      <div>
        <h1 className="onboarding-hero-title text-2xl font-bold tracking-wide md:text-3xl">
          LUMINA Neural Command Deck
        </h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Progressive onboarding — only the steps you need
        </p>
      </div>
    </div>
  );
}
