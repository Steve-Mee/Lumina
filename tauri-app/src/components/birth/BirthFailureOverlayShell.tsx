import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

interface BirthFailureOverlayShellProps {
  title: string;
  subtitle?: string | null;
  meta?: ReactNode;
  error?: string | null;
  children?: ReactNode;
  actions?: ReactNode;
  className?: string;
}

export function BirthFailureOverlayShell({
  title,
  subtitle,
  meta,
  error,
  children,
  actions,
  className,
}: BirthFailureOverlayShellProps) {
  return (
    <div
      className={cn(
        "birth-failure-overlay pointer-events-auto absolute inset-0 z-50 flex items-center justify-center overflow-y-auto px-4 py-10",
        className,
      )}
    >
      <div className="birth-failure-overlay__card pointer-events-auto w-full max-w-2xl space-y-5">
        <div className="text-center">
          <h2 className="birth-phase-headline text-2xl font-semibold tracking-wide md:text-3xl">
            {title}
          </h2>
          {subtitle ? (
            <p className="birth-phase-subtitle mt-2 text-sm text-muted-foreground">{subtitle}</p>
          ) : null}
          {meta}
          {error ? <p className="mt-2 text-xs text-destructive">{error}</p> : null}
        </div>
        {children}
        {actions}
      </div>
    </div>
  );
}
