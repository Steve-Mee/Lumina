import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { startBirthSession, type BirthStatusPayload } from "@/lib/birthClient";
import {
  birthProgressDiagnostics,
  checkpointTradeCount,
  detectBirthRecoveryKind,
  type BirthRecoveryKind,
} from "@/lib/birthRecoveryModel";
import { useBirthStore } from "@/store/birthStore";
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
};

async function runBirthAction(
  label: string,
  action: () => Promise<unknown>,
): Promise<void> {
  try {
    await action();
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
        "rounded-lg border border-amber-500/30 bg-amber-950/20 p-4 text-sm text-amber-100/90",
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

        {kind === "checkpoint_available" ? (
          <>
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
            <Button
              type="button"
              size="sm"
              variant="outline"
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

        {onDismiss ? (
          <Button type="button" size="sm" variant="ghost" onClick={onDismiss}>
            Dismiss
          </Button>
        ) : null}
      </div>
    </div>
  );
}
