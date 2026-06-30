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
  default: "text-foreground",
  success: "text-emerald-300",
  warn: "text-amber-300",
  accent: "text-cyan-200",
};

export function BirthKpiTile({
  label,
  value,
  detail,
  tone = "default",
  className,
}: BirthKpiTileProps) {
  return (
    <div className={cn("birth-kpi-tile lumina-glass lumina-glass--panel transition-colors", className)}>
      <p className="birth-kpi-tile__label font-mono text-[10px] tracking-wide text-muted-foreground uppercase">
        {label}
      </p>
      <p className={cn("birth-kpi-tile__value mt-0.5 font-mono text-base font-semibold tabular-nums", TONE_CLASS[tone])}>
        {value}
      </p>
      {detail ? (
        <p className="birth-kpi-tile__detail mt-0.5 font-mono text-[10px] text-muted-foreground">{detail}</p>
      ) : null}
    </div>
  );
}
