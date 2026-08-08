import type { ReactNode } from "react";

import { HelpTip } from "@/components/ui/HelpTip";
import {
  CONDITION_VALUE_TEXT_CLASS,
  type ConditionTone,
} from "@/lib/conditionTone";
import { cn } from "@/lib/utils";

/** @deprecated Prefer ConditionTone from @/lib/conditionTone — same values. */
export type BirthFieldTone = ConditionTone;

interface BirthFieldCardProps {
  label: string;
  value?: ReactNode;
  hint?: string;
  tip?: string;
  tone?: BirthFieldTone;
  className?: string;
  children?: ReactNode;
}

/** Vault / Risk Envelope field card — fixed label, live mono value, optional hint. */
export function BirthFieldCard({
  label,
  value,
  hint,
  tip,
  tone = "default",
  className,
  children,
}: BirthFieldCardProps) {
  return (
    <div
      className={cn("risk-envelope-field-card birth-field-card", className)}
      data-tone={tone === "default" ? undefined : tone}
    >
      <div className="mb-0.5 flex items-center gap-1.5">
        <p className="risk-envelope-field-label mb-0">{label}</p>
        {tip ? <HelpTip text={tip} /> : null}
      </div>
      {children ?? (
        <p
          className={cn(
            "font-mono text-sm tabular-nums tracking-tight",
            CONDITION_VALUE_TEXT_CLASS[tone],
          )}
        >
          {value ?? "—"}
        </p>
      )}
      {hint ? (
        <p className="risk-envelope-field-hint mt-0.5 truncate" title={hint}>
          {hint}
        </p>
      ) : null}
    </div>
  );
}

interface BirthSectionCardProps {
  title: string;
  children: ReactNode;
  className?: string;
}

/** Named section wrapper for grouped field grids. */
export function BirthSectionCard({ title, children, className }: BirthSectionCardProps) {
  return (
    <div className={cn("birth-section-card space-y-1.5", className)}>
      <p className="font-mono text-[0.55rem] tracking-[0.14em] text-cyan-200/80 uppercase">
        {title}
      </p>
      <div className="birth-intel-field-grid">{children}</div>
    </div>
  );
}
