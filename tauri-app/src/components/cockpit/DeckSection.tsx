import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

interface DeckSectionProps {
  title?: string;
  icon?: LucideIcon;
  children: ReactNode;
  className?: string;
  titleClassName?: string;
}

export function DeckSection({
  title,
  icon: Icon,
  children,
  className,
  titleClassName,
}: DeckSectionProps) {
  return (
    <section className={cn("deck-section", className)}>
      {title ? (
        <div className="mb-2 flex items-center gap-2">
          {Icon ? <Icon className={cn("size-3.5 shrink-0 deck-accent-text", titleClassName)} /> : null}
          <h4 className={cn("deck-section__title", titleClassName)}>{title}</h4>
        </div>
      ) : null}
      {children}
    </section>
  );
}
