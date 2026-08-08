import type { ReactNode } from "react";

import { HelpTip } from "@/components/ui/HelpTip";
import type { ConditionTone } from "@/lib/conditionTone";
import { cn } from "@/lib/utils";

export function FieldCard({
  label,
  tip,
  hint,
  children,
  className,
  tone = "default",
}: {
  label: string;
  tip?: string;
  hint?: string;
  children: ReactNode;
  className?: string;
  /** Condition status: ok=green, warn=orange, danger=red. */
  tone?: ConditionTone;
}) {
  return (
    <div
      className={cn("risk-envelope-field-card", className)}
      data-tone={tone === "default" || tone === "accent" ? undefined : tone}
    >
      <div className="mb-1 flex items-center gap-1.5">
        <p className="risk-envelope-field-label mb-0">{label}</p>
        {tip ? <HelpTip text={tip} /> : null}
      </div>
      {children}
      {hint ? <p className="risk-envelope-field-hint">{hint}</p> : null}
    </div>
  );
}

export function ToggleRow({
  label,
  tip,
  hint,
  checked,
  onChange,
  warn,
}: {
  label: string;
  tip?: string;
  hint?: string;
  checked: boolean;
  onChange: (next: boolean) => void;
  warn?: string | null;
}) {
  return (
    <label className="risk-envelope-toggle-row">
      <input
        type="checkbox"
        className="mt-0.5 size-3.5 shrink-0 accent-cyan-400"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
      />
      <span className="min-w-0 flex-1">
        <span className="flex items-center gap-1.5">
          <span className="text-sm text-foreground/90">{label}</span>
          {tip ? <HelpTip text={tip} /> : null}
        </span>
        {hint ? <span className="mt-0.5 block text-[11px] text-muted-foreground">{hint}</span> : null}
        {warn ? <span className="mt-0.5 block text-[11px] text-amber-300/85">{warn}</span> : null}
      </span>
    </label>
  );
}

export function ConfigRange({
  label,
  value,
  min,
  max,
  step,
  format,
  onChange,
  hideLabel = false,
  hot = false,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  format: (value: number) => string;
  onChange: (value: number) => void;
  hideLabel?: boolean;
  hot?: boolean;
}) {
  const pct = max === min ? 0 : ((value - min) / (max - min)) * 100;

  return (
    <div className={cn("risk-envelope-slider", hot && "risk-envelope-slider--hot")}>
      {!hideLabel ? (
        <label className="mb-1 flex justify-between text-xs text-muted-foreground uppercase">
          <span>{label}</span>
          <span className={cn("font-mono", hot && "text-amber-300")}>{format(value)}</span>
        </label>
      ) : (
        <div className="mb-1.5 flex justify-end">
          <span
            className={cn(
              "font-mono text-sm tabular-nums",
              hot ? "text-amber-300" : "text-cyan-200/90",
            )}
          >
            {format(value)}
          </span>
        </div>
      )}
      <div className="risk-envelope-slider__track-wrap">
        <div
          className="risk-envelope-slider__fill"
          style={{ width: `${pct}%` }}
          aria-hidden
        />
        <input
          type="range"
          className="risk-envelope-slider__input config-range w-full"
          min={min}
          max={max}
          step={step}
          value={value}
          aria-label={label}
          onChange={(e) => onChange(Number(e.target.value))}
        />
      </div>
    </div>
  );
}
