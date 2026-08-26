import type { ReactNode } from "react";

import { HelpTip } from "@/components/ui/HelpTip";
import { cn } from "@/lib/utils";

export const RESUME_TIER_HINT: Record<string, string> = {
  T0: "Latest cache loaded directly.",
  T1: "Checkpoint manifest restored from cache.",
  T2: "Regime map recomputed (algo update); curriculum intact.",
  T3: "Data re-prepared; curriculum intact.",
  T4: "New market data — holdout recomputed; curriculum intact.",
};

export function StatusChip({
  label,
  state,
  tip,
}: {
  label: string;
  state: "ok" | "partial" | "warn" | "idle";
  tip: string;
}) {
  return (
    <span
      className="risk-envelope-status-chip"
      data-state={state === "idle" ? undefined : state}
      title={tip}
    >
      <span className="risk-envelope-status-chip__dot" />
      {label}
    </span>
  );
}

export function RecoveryActionCard({
  label,
  tip,
  hint,
  tone = "default",
  children,
}: {
  label: string;
  tip?: string;
  hint: string;
  tone?: "default" | "accent" | "warn" | "danger";
  children: ReactNode;
}) {
  return (
    <div
      className={cn(
        "risk-envelope-field-card genesis-recovery-action-card h-full",
        tone === "accent" && "genesis-recovery-action-card--accent",
        tone === "warn" && "genesis-recovery-action-card--warn",
        tone === "danger" && "genesis-recovery-action-card--danger",
      )}
    >
      <div className="mb-2 flex items-center justify-center gap-1.5">
        <p className="risk-envelope-field-label mb-0">{label}</p>
        {tip ? <HelpTip text={tip} /> : null}
      </div>
      <div className="genesis-recovery-action-card__body">{children}</div>
      <p className="risk-envelope-field-hint mt-auto pt-2 text-center">{hint}</p>
    </div>
  );
}

export function CharterTile({
  label,
  value,
  tip,
  footnote,
}: {
  label: string;
  value: string;
  tip: string;
  footnote: string;
}) {
  return (
    <div className="risk-envelope-field-card genesis-charter-tile genesis-charter-tile--centered flex h-full flex-col items-center text-center">
      <div className="mb-1 flex items-center justify-center gap-1.5">
        <p className="risk-envelope-field-label mb-0">{label}</p>
        <HelpTip text={tip} />
      </div>
      <p className="font-mono text-lg tabular-nums tracking-tight text-cyan-100 sm:text-xl">
        {value}
      </p>
      <p className="risk-envelope-field-hint mt-auto w-full pt-1 text-center">{footnote}</p>
    </div>
  );
}

export function DataPolicyCard({
  label,
  tip,
  hint,
  checked,
  disabled,
  onChange,
  controlLabel,
}: {
  label: string;
  tip?: string;
  hint: string;
  checked: boolean;
  disabled?: boolean;
  onChange: (next: boolean) => void;
  controlLabel: string;
}) {
  return (
    <div className="risk-envelope-field-card genesis-data-policy-card h-full">
      <div className="mb-2 flex items-center justify-center gap-1.5">
        <p className="risk-envelope-field-label mb-0">{label}</p>
        {tip ? <HelpTip text={tip} /> : null}
      </div>
      <label className="genesis-data-policy-card__control">
        <input
          type="checkbox"
          className="size-4 shrink-0 accent-cyan-400"
          checked={checked}
          disabled={disabled}
          onChange={(e) => onChange(e.target.checked)}
        />
        <span className="text-sm font-medium text-foreground/90">{controlLabel}</span>
      </label>
      <p className="risk-envelope-field-hint mt-auto pt-2 text-center">{hint}</p>
    </div>
  );
}
