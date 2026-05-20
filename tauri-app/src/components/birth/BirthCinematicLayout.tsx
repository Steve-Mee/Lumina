import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

interface BirthCinematicLayoutProps {
  stage: ReactNode;
  deck: ReactNode;
  className?: string;
}

export function BirthCinematicLayout({ stage, deck, className }: BirthCinematicLayoutProps) {
  return (
    <div className={cn("birth-activation-screen w-full max-w-none", className)}>
      <div className="birth-activation-grid mx-auto flex min-h-[calc(100vh-6rem)] w-full max-w-6xl flex-col md:min-h-[calc(100vh-5rem)] md:flex-row md:items-stretch md:gap-0">
        <div className="birth-activation-stage flex min-h-[320px] flex-1 flex-col justify-center md:min-h-0 md:basis-[72%]">
          {stage}
        </div>
        <div className="birth-activation-deck lumina-glass lumina-glass--overlay flex flex-col justify-end md:justify-center md:basis-[28%]">
          {deck}
        </div>
      </div>
    </div>
  );
}
