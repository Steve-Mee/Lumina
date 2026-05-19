import type { ReactNode } from "react";

import { LuminaLogo } from "@/components/cockpit/LuminaLogo";
import { cn } from "@/lib/utils";

interface OnboardingShellProps {
  children: ReactNode;
  className?: string;
}

export function OnboardingShell({ children, className }: OnboardingShellProps) {
  return (
    <div
      className={cn(
        "onboarding-shell relative flex min-h-screen flex-col overflow-hidden text-foreground",
        className,
      )}
    >
      <div className="cockpit-stars pointer-events-none absolute inset-0 opacity-50" />
      <div className="cockpit-grid pointer-events-none absolute inset-0 opacity-30" />
      <div className="relative z-10 flex min-h-0 flex-1 flex-col">{children}</div>
    </div>
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
