import type { ReactNode } from "react";

import {
  analyticsAnnexClass,
  analyticsAnnexCssVars,
} from "@/lib/analyticsAnnexPresentation";
import { selectCurrentMode, useCoreStore } from "@/store/coreStore";
import { cn } from "@/lib/utils";

interface AnalyticsAnnexShellProps {
  subtitle: string;
  label?: string;
  className?: string;
  children: ReactNode;
}

export function AnalyticsAnnexShell({
  subtitle,
  label = "Analytics Annex",
  className,
  children,
}: AnalyticsAnnexShellProps) {
  const operatorMode = useCoreStore(selectCurrentMode);

  return (
    <div
      className={cn(
        analyticsAnnexClass(),
        "flex min-h-0 flex-1 flex-col overflow-hidden rounded-md border",
        className,
      )}
      style={analyticsAnnexCssVars(operatorMode)}
    >
      <header className="shrink-0 border-b px-3 py-2" style={{ borderColor: "var(--annex-border)" }}>
        <p className="font-mono text-[10px] tracking-[0.14em] uppercase" style={{ color: "var(--annex-muted)" }}>
          {label} · {subtitle}
        </p>
      </header>
      <div className="analytics-annex__body min-h-0 flex-1 overflow-y-auto [scrollbar-width:thin]">
        {children}
      </div>
    </div>
  );
}
