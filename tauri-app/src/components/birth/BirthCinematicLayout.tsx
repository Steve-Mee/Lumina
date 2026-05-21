import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

interface BirthCinematicLayoutProps {
  stage: ReactNode;
  deck: ReactNode;
  className?: string;
  stageCharging?: boolean;
}

export function BirthCinematicLayout({
  stage,
  deck,
  className,
  stageCharging = false,
}: BirthCinematicLayoutProps) {
  return (
    <div
      className={cn(
        "birth-activation-screen birth-activation-screen--anchored flex min-h-0 w-full max-w-none flex-1 flex-col",
        className,
      )}
    >
      <div className="birth-activation-stack mx-auto h-full min-h-0 w-full max-w-6xl flex-1">
        <div
          className={cn(
            "birth-activation-helix-arena flex min-h-0 flex-col",
            stageCharging && "birth-activation-helix-arena--charge",
          )}
        >
          {stage}
        </div>
        <div className="birth-activation-deck lumina-glass lumina-glass--overlay flex min-h-0 min-w-0 flex-col">
          {deck}
        </div>
      </div>
    </div>
  );
}
