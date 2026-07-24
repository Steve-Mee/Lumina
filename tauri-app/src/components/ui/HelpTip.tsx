import { HelpCircle } from "lucide-react";

import { cn } from "@/lib/utils";

interface HelpTipProps {
  text: string;
  className?: string;
  label?: string;
}

/** Compact info control for first-time operators (native title tooltip). */
export function HelpTip({ text, className, label = "More info" }: HelpTipProps) {
  return (
    <button
      type="button"
      className={cn(
        "inline-flex size-4 shrink-0 items-center justify-center rounded-full",
        "text-cyan-300/70 transition-colors hover:text-cyan-200",
        "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-cyan-400/50",
        className,
      )}
      title={text}
      aria-label={label}
    >
      <HelpCircle className="size-3.5" aria-hidden />
    </button>
  );
}
