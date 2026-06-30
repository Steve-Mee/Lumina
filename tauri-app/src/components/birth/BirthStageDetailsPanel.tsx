import { useEffect, useRef, useState } from "react";
import { ChevronDown } from "lucide-react";

import type { BirthProgressPayload } from "@/lib/birthClient";
import { extractStageScorecard } from "@/lib/birthPhaseModel";
import { cn } from "@/lib/utils";

import { BirthStageScorecard } from "@/components/birth/BirthStageScorecard";

interface BirthStageDetailsPanelProps {
  progress: BirthProgressPayload | undefined;
  className?: string;
}

export function BirthStageDetailsPanel({ progress, className }: BirthStageDetailsPanelProps) {
  const scorecard = extractStageScorecard(progress);
  const hasBlocker = Boolean(scorecard?.blockerDetail);
  const [open, setOpen] = useState(hasBlocker);
  const toggleRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (hasBlocker) {
      setOpen(true);
    }
  }, [hasBlocker]);

  const handleToggle = () => {
    setOpen((value) => {
      const next = !value;
      if (next) {
        requestAnimationFrame(() => {
          toggleRef.current?.scrollIntoView({ block: "nearest" });
        });
      }
      return next;
    });
  };

  if (!scorecard) {
    return null;
  }

  return (
    <div className={cn("birth-stage-details rounded-lg border border-white/8", className)}>
      <button
        ref={toggleRef}
        type="button"
        className="birth-stage-details__toggle flex w-full items-center justify-between gap-2 px-3 py-2 text-left"
        aria-expanded={open}
        onClick={handleToggle}
      >
        <span className="font-mono text-[10px] tracking-wide text-cyan-200/90 uppercase">
          Stage details
        </span>
        <ChevronDown
          className={cn(
            "size-3.5 shrink-0 text-muted-foreground transition-transform",
            open && "rotate-180",
          )}
        />
      </button>
      {open ? (
        <div className="birth-stage-details__content border-t border-white/5 px-3 py-2">
          <BirthStageScorecard progress={progress} />
        </div>
      ) : null}
    </div>
  );
}
