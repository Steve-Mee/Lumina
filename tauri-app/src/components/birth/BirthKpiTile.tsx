import { cn } from "@/lib/utils";

export type BirthKpiTone = "default" | "success" | "warn" | "accent";

interface BirthKpiTileProps {
  label: string;
  value: string;
  detail?: string;
  tone?: BirthKpiTone;
  className?: string;
}

const TONE_CLASS: Record<BirthKpiTone, string> = {
  default: "text-cyan-100",
  success: "text-emerald-300",
  warn: "text-amber-300",
  accent: "text-cyan-200",
};

/** Genesis CharterTile-style KPI — fixed label, mono value, footnote. */
export function BirthKpiTile({
  label,
  value,
  detail,
  tone = "default",
  className,
}: BirthKpiTileProps) {
  return (
    <div
      className={cn(
        "birth-kpi-tile risk-envelope-field-card flex h-full flex-col",
        className,
      )}
    >
      <p className="risk-envelope-field-label mb-0.5">{label}</p>
      <p
        className={cn(
          "birth-kpi-tile__value font-mono text-base font-semibold tabular-nums tracking-tight",
          TONE_CLASS[tone],
        )}
      >
        {value}
      </p>
      {detail ? (
        <p className="risk-envelope-field-hint mt-auto pt-0.5">{detail}</p>
      ) : null}
    </div>
  );
}
