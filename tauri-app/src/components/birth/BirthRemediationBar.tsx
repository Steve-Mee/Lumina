import type { BirthStatusPayload } from "@/lib/birthClient";
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
    <div className={cn("rounded-md border border-amber-500/30 bg-black/30 px-3 py-2", className)}>
      <div className="flex items-center justify-between gap-2 text-[10px] font-mono uppercase tracking-wide text-amber-100/90">
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
