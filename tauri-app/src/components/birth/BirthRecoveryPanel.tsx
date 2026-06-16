import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { startBirthSession, isBirthStartSuccessful, reuseDataBirthSession, type BirthStatusPayload } from "@/lib/birthClient";
import {
  birthProgressDiagnostics,
  checkpointTradeCount,
  detectBirthRecoveryKind,
  type BirthRecoveryKind,
} from "@/lib/birthRecoveryModel";
import { useBirthStore } from "@/store/birthStore";
import { warnOverlayPanelClass } from "@/lib/modePresentation";
import { cn } from "@/lib/utils";

interface BirthRecoveryPanelProps {
  status: BirthStatusPayload | null;
  targetTrades: number;
  className?: string;
  onDismiss?: () => void;
}

const COPY: Record<
  Exclude<BirthRecoveryKind, null>,
  { title: string; body: string }
> = {
  history_unavailable: {
    title: "Historical data unavailable",
    body: "Real historical data could not be loaded. Retry with real data, or start a practice run with synthetic data (does not count toward live readiness).",
  },
  checkpoint_available: {
    title: "Checkpoint available",
    body: "A birth checkpoint was found. Resume from checkpoint or force a fresh start.",
  },
  simulation_stall: {
    title: "Simulation stall",
    body: "The SIM chunk produced no trades. Retry from the last checkpoint or review diagnostics below.",
  },
  session_interrupted: {
    title: "Birth session interrupted",
    body: "A previous birth run was stopped before completion. Resume from the last checkpoint or start fresh.",
  },
  certificate_failed: {
    title: "Certificate thresholds not met",
    body: "OOS evaluation failed. Continue from checkpoint, reuse loaded data, or wipe and restart.",
  },
};

async function runBirthAction(
  label: string,
  action: () => Promise<Record<string, unknown>>,
): Promise<void> {
  try {
    const result = await action();
    const status = String(result.status ?? "");
    if (!isBirthStartSuccessful(status)) {
      toast.error(String(result.message ?? `Birth action failed (${status || "unknown"})`));
      return;
    }
    useBirthStore.setState({ uiPhase: "running", pollError: null });
    await useBirthStore.getState().poll();
    toast.success(label);
  } catch (err) {
    toast.error(err instanceof Error ? err.message : "Birth action failed");
  }
}

export function BirthRecoveryPanel({
  status,
  targetTrades,
  className,
  onDismiss,
}: BirthRecoveryPanelProps) {
  const kind = detectBirthRecoveryKind(status);
  if (!kind) {
    return null;
  }

  const copy = COPY[kind];
  const diagnostics = birthProgressDiagnostics(status?.progress);
  const ckptTrades = checkpointTradeCount(status?.progress);

  return (
    <div
      className={cn(
        "rounded-lg p-4 text-sm text-amber-100/90",
        warnOverlayPanelClass(),
        className,
      )}
    >
      <p className="font-medium text-amber-100">{copy.title}</p>
      <p className="mt-1 text-xs leading-relaxed text-amber-100/75">{copy.body}</p>

      {kind === "checkpoint_available" && ckptTrades > 0 ? (
        <p className="mt-2 font-mono text-[10px] text-muted-foreground">
          Checkpoint trades: {ckptTrades.toLocaleString()}
        </p>
      ) : null}

      {diagnostics ? (
        <pre className="mt-2 max-h-24 overflow-auto rounded border border-white/10 bg-black/30 p-2 font-mono text-[9px] text-muted-foreground">
          {diagnostics}
        </pre>
      ) : null}

      <div className="mt-4 flex flex-wrap gap-2">
        {kind === "history_unavailable" ? (
          <>
            <Button
              type="button"
              size="sm"
              variant="secondary"
              onClick={() =>
                void runBirthAction("Retrying with real data…", () =>
                  startBirthSession({ targetTrades, force: true }),
                )
              }
            >
              Retry real data
            </Button>
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={() =>
                void runBirthAction("Practice run started (synthetic)", () =>
                  startBirthSession({ targetTrades, practiceMode: true, force: true }),
                )
              }
            >
              Start practice (synthetic)
            </Button>
          </>
        ) : null}

        {kind === "session_interrupted" || kind === "checkpoint_available" ? (
          <>
            {kind === "checkpoint_available" ? (
              <Button
                type="button"
                size="sm"
                variant="secondary"
                onClick={() =>
                  void runBirthAction("Resuming from checkpoint…", () =>
                    startBirthSession({
                      targetTrades,
                      continueTraining: true,
                      practiceMode: true,
                    }),
                  )
                }
              >
                Resume practice checkpoint
              </Button>
            ) : null}
            <Button
              type="button"
              size="sm"
              variant={kind === "session_interrupted" ? "secondary" : "outline"}
              onClick={() =>
                void runBirthAction("Resuming certified checkpoint…", () =>
                  startBirthSession({ targetTrades, continueTraining: true }),
                )
              }
            >
              Resume certified checkpoint
            </Button>
            <Button
              type="button"
              size="sm"
              variant="ghost"
              onClick={() =>
                void runBirthAction("Fresh birth started", () =>
                  startBirthSession({ targetTrades, force: true }),
                )
              }
            >
              Force fresh start
            </Button>
          </>
        ) : null}

        {kind === "simulation_stall" ? (
          <Button
            type="button"
            size="sm"
            variant="secondary"
            onClick={() =>
              void runBirthAction("Retrying from checkpoint…", () =>
                startBirthSession({ targetTrades, continueTraining: true }),
              )
            }
          >
            Retry from checkpoint
          </Button>
        ) : null}

        {kind === "certificate_failed" ? (
          <>
            <Button
              type="button"
              size="sm"
              variant="secondary"
              onClick={() =>
                void runBirthAction("Continuing from checkpoint…", () =>
                  startBirthSession({ targetTrades, continueTraining: true }),
                )
              }
            >
              Continue learning
            </Button>
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={() =>
                void (async () => {
                  try {
                    const result = await reuseDataBirthSession(targetTrades);
                    if (!isBirthStartSuccessful(result.status)) {
                      toast.error(String(result.message ?? "Reuse data failed"));
                      return;
                    }
                    useBirthStore.setState({ uiPhase: "running", pollError: null });
                    await useBirthStore.getState().poll();
                    toast.success("Reusing data manifest from checkpoint");
                  } catch (err) {
                    toast.error(err instanceof Error ? err.message : "Reuse data failed");
                  }
                })()
              }
            >
              Reuse data & retry
            </Button>
            {status?.quality_score != null ? (
              <p className="w-full font-mono text-[10px] text-muted-foreground">
                Quality score: {Number(status.quality_score).toFixed(1)}
              </p>
            ) : null}
          </>
        ) : null}

        {onDismiss ? (
          <Button type="button" size="sm" variant="ghost" onClick={onDismiss}>
            Dismiss
          </Button>
        ) : null}
      </div>
    </div>
  );
}
