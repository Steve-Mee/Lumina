import type { BirthStatusPayload } from "@/lib/birthClient";
import { distressPanelClass } from "@/lib/modePresentation";
import { cn } from "@/lib/utils";

interface BirthRemediationBarProps {
  status: BirthStatusPayload | null;
  className?: string;
}

export function BirthRemediationBar({ status, className }: BirthRemediationBarProps) {
  const progress = status?.progress;
  const attempt = Number(status?.remediation_attempt ?? progress?.remediation_attempt ?? 0);
  const max = Number(status?.remediation_max ?? progress?.remediation_max ?? 0);
  const phase = String(progress?.phase ?? status?.checkpoint_phase ?? "").toLowerCase();
  const running = String(status?.status ?? "").toLowerCase() === "running";
  const runwayPhase = String(status?.runway_phase ?? progress?.runway_phase ?? "").trim();

  const remediationExhausted = max > 0 && attempt >= max;
  const runwayResume =
    phase === "certificate_failed" && (Boolean(runwayPhase) || remediationExhausted);

  if (runwayResume) {
    const label = runwayPhase
      ? `Certificate retry: ${runwayPhase} (Proving Ground, not Birth)`
      : "Certificate OOS is Proving Ground — not a Birth stage";
    return (
      <div className={cn("birth-info-callout rounded-md px-3 py-2", className)}>
        <p className="birth-info-callout__text text-[10px] uppercase tracking-wide">{label}</p>
        <p className="mt-1 text-[10px] text-muted-foreground">
          Continue learning re-enters the certificate pipeline after Birth Foundation. S1–S5 plant receipts stay.
        </p>
      </div>
    );
  }

  if (!max || attempt <= 0) {
    return null;
  }
  const visible =
    phase === "certificate_remediation" ||
    running ||
    String(status?.status ?? "").toLowerCase() === "certificate_failed";
  if (!visible) {
    return null;
  }

  const pct = Math.min(100, Math.max(0, (attempt / max) * 100));
  const action = String((progress as Record<string, unknown> | undefined)?.remediation_action ?? "");

  return (
    <div className={cn("rounded-md px-3 py-2", distressPanelClass("warn"), className)}>
      <div className="birth-distress-callout__title flex items-center justify-between gap-2 tracking-wide">
        <span>Certificate remediation</span>
        <span>
          {attempt}/{max}
        </span>
      </div>
      <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-white/10">
        <div className="h-full rounded-full bg-amber-400/80 transition-all" style={{ width: `${pct}%` }} />
      </div>
      {action ? (
        <p className="mt-2 text-[10px] text-muted-foreground">Action: {action.replace(/_/g, " ")}</p>
      ) : null}
    </div>
  );
}
