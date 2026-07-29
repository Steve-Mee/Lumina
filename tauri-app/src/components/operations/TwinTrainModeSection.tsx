import { Shield } from "lucide-react";

import { DeckSection } from "@/components/cockpit/DeckSection";
import { Button } from "@/components/ui/button";
import {
  isModeReady,
  promotionRatio,
  type TwinMetrics,
  type TwinModeStatus,
  type TwinModeTarget,
} from "@/lib/twinClient";
import { cn } from "@/lib/utils";

function readinessFailReasons(value: unknown): string[] {
  if (!value || typeof value !== "object") return [];
  const rec = value as Record<string, unknown>;
  if (Array.isArray(rec.fail_reasons)) {
    return rec.fail_reasons.map(String).filter(Boolean);
  }
  if (typeof rec.reason === "string" && rec.reason.trim()) {
    return [rec.reason.trim()];
  }
  return [];
}

export interface TwinTrainModeSectionProps {
  metrics: TwinMetrics | null;
  modeStatus: TwinModeStatus | null;
  busyKey: string | null;
  onPromote: (target: TwinModeTarget) => void;
}

export function TwinTrainModeSection({
  metrics,
  modeStatus,
  busyKey,
  onPromote,
}: TwinTrainModeSectionProps) {
  const mode = String(modeStatus?.mode ?? metrics?.mode ?? "shadow");
  const authority = String(modeStatus?.authority ?? metrics?.authority ?? "—");
  const readiness = modeStatus?.readiness ?? metrics?.mode_readiness ?? null;
  const modeProgress =
    modeStatus?.mode_promotion_progress ?? metrics?.mode_promotion_progress ?? null;
  const assistedProgress = modeProgress?.progress?.assisted;
  const fullAutoProgress = modeProgress?.progress?.full_auto;
  const assistedReady =
    isModeReady(readiness?.assisted) || Boolean(assistedProgress?.ready);
  const fullAutoReady =
    isModeReady(readiness?.full_auto) || Boolean(fullAutoProgress?.ready);
  const assistedReasons =
    readinessFailReasons(readiness?.assisted).length > 0
      ? readinessFailReasons(readiness?.assisted)
      : (assistedProgress?.fail_reasons ?? []).map(String);
  const fullAutoReasons =
    readinessFailReasons(readiness?.full_auto).length > 0
      ? readinessFailReasons(readiness?.full_auto)
      : (fullAutoProgress?.fail_reasons ?? []).map(String);

  return (
    <DeckSection title="Judgment mode" icon={Shield}>
      <div className="flex flex-wrap items-center gap-2">
        <span className="rounded bg-violet-500/20 px-2 py-0.5 font-mono text-[10px] tracking-wider text-violet-100 uppercase">
          {mode}
        </span>
        <span className="font-mono text-[10px] text-muted-foreground">
          authority: {authority}
        </span>
        <span
          className={cn(
            "rounded px-1.5 py-0.5 font-mono text-[9px] uppercase tracking-wider",
            assistedReady
              ? "bg-emerald-500/15 text-emerald-200"
              : "bg-muted/40 text-muted-foreground",
          )}
        >
          assisted {assistedReady ? "ready" : "gated"}
        </span>
        <span
          className={cn(
            "rounded px-1.5 py-0.5 font-mono text-[9px] uppercase tracking-wider",
            fullAutoReady
              ? "bg-emerald-500/15 text-emerald-200"
              : "bg-muted/40 text-muted-foreground",
          )}
        >
          full_auto {fullAutoReady ? "ready" : "gated"}
        </span>
      </div>
      <p className="mt-1.5 text-[10px] text-muted-foreground">
        Promote only when measurable gates pass (agreement, FP rate, constitution, samples).
        Fail-closed — blocked promotions show why.
      </p>
      {assistedProgress || fullAutoProgress ? (
        <div className="mt-2 space-y-1.5">
          {(
            [
              ["assisted", assistedProgress],
              ["full_auto", fullAutoProgress],
            ] as const
          ).map(([label, prog]) => {
            if (!prog) return null;
            const sampleR = promotionRatio(prog.samples);
            const agreeR = promotionRatio(prog.agreement);
            const fpR = promotionRatio(prog.false_positive);
            return (
              <div key={label} className="space-y-0.5">
                <p className="font-mono text-[9px] tracking-wider text-muted-foreground uppercase">
                  {label} progress · samples {(sampleR * 100).toFixed(0)}% · agree{" "}
                  {(agreeR * 100).toFixed(0)}% · fp room {(fpR * 100).toFixed(0)}%
                </p>
                <div className="flex h-1.5 gap-0.5 overflow-hidden rounded bg-muted/40">
                  <div
                    className="bg-violet-400/80 transition-all"
                    style={{ width: `${sampleR * 33.3}%` }}
                    title="samples"
                  />
                  <div
                    className="bg-emerald-400/80 transition-all"
                    style={{ width: `${agreeR * 33.3}%` }}
                    title="agreement"
                  />
                  <div
                    className="bg-cyan-400/70 transition-all"
                    style={{ width: `${fpR * 33.3}%` }}
                    title="fp room"
                  />
                </div>
              </div>
            );
          })}
        </div>
      ) : null}
      {!assistedReady && assistedReasons.length > 0 ? (
        <p className="mt-1 font-mono text-[9px] text-amber-200/75">
          assisted gates: {assistedReasons.slice(0, 4).join("; ")}
        </p>
      ) : null}
      {!fullAutoReady && fullAutoReasons.length > 0 ? (
        <p className="mt-0.5 font-mono text-[9px] text-amber-200/75">
          full_auto gates: {fullAutoReasons.slice(0, 4).join("; ")}
        </p>
      ) : null}
      <div className="mt-2 flex flex-wrap gap-2">
        <Button
          type="button"
          size="xs"
          variant="secondary"
          disabled={busyKey !== null || mode === "assisted" || mode === "full_auto"}
          title={
            assistedReady
              ? "Promote to assisted when gates pass"
              : assistedReasons[0] ?? "Gate not ready (still allowed to try — server is SSOT)"
          }
          onClick={() => onPromote("assisted")}
        >
          Promote assisted
        </Button>
        <Button
          type="button"
          size="xs"
          variant="secondary"
          disabled={busyKey !== null || mode === "full_auto"}
          title={
            fullAutoReady
              ? "Promote to full_auto when gates pass"
              : fullAutoReasons[0] ?? "Gate not ready (still allowed to try — server is SSOT)"
          }
          onClick={() => onPromote("full_auto")}
        >
          Promote full_auto
        </Button>
      </div>
    </DeckSection>
  );
}
