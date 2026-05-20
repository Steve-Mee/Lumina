import type { ReactNode } from "react";

import { AnalyticsAnnexShell } from "@/components/cockpit/AnalyticsAnnexShell";
import { cn } from "@/lib/utils";

interface ObservationDeckFrameProps {
  subtitle: string;
  label?: string;
  className?: string;
  children: ReactNode;
  inset?: boolean;
}

export function ObservationDeckFrame({
  subtitle,
  label = "Observation Deck",
  className,
  children,
  inset = false,
}: ObservationDeckFrameProps) {
  return (
    <AnalyticsAnnexShell subtitle={subtitle} label={label} className={className}>
      <div className={cn(inset && "deck-annex-inset p-2", !inset && "p-2")}>{children}</div>
    </AnalyticsAnnexShell>
  );
}
