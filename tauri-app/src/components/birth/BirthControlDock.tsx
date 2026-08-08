import { Loader2, OctagonPause, Play, RotateCcw, Trash2 } from "lucide-react";import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import type { BirthWipeResult } from "@/lib/birthClient";
import { traceBirthWipe } from "@/lib/birthWipeTrace";
import { cn } from "@/lib/utils";
import { luminaInteractiveClass } from "@/lib/glassGlowTaxonomy";
import { useBirthUiStore, type WipeConfirmKind } from "@/store/birthUiStore";

export type BirthControlMode = "running" | "genesis";

const RESUME_CHECKPOINT_HINT =
  "Ga verder bij laatste stage/PPO-steps. Data-prep kan kort opnieuw draaien; curriculum wordt niet gewist.";

interface BirthControlDockProps {
  mode: BirthControlMode;
  checkpointAvailable?: boolean;
  busy?: boolean;
  /** Birth launch sequencing — separate from busy for clearer wipe-block feedback. */
  activating?: boolean;
  /** Show Stop birth on genesis surface while backend engine is still live. */
  engineLive?: boolean;
  inline?: boolean;
  /** When false, genesis mode omits Start birth (e.g. deck uses BirthLaunchButton). */
  showStartButton?: boolean;
  onStop?: () => void | Promise<void>;
  onStart?: () => void;
  /** @deprecated Wipe confirm runs via BirthConfirmHost + birthUiStore */
  onWipe?: () => Promise<BirthWipeResult>;
  onResumeCheckpoint?: () => void;
  className?: string;
}

export function BirthControlDock({
  mode,
  checkpointAvailable = false,
  busy = false,
  activating = false,
  engineLive = false,
  inline = false,
  showStartButton = true,
  onStart,
  onResumeCheckpoint,
  className,
}: BirthControlDockProps) {
  const wipeConfirmWiping = useBirthUiStore((s) => s.wipeConfirmWiping);
  const openWipeConfirm = useBirthUiStore((s) => s.openWipeConfirm);
  const openStopConfirm = useBirthUiStore((s) => s.openStopConfirm);

  const wipeBlocked = busy || activating || wipeConfirmWiping;
  const stopBlocked = busy;

  const handleStopClick = () => {
    if (busy) {
      toast.info("Please wait — another birth action is in progress.");
      return;
    }
    openStopConfirm();
  };

  const handleWipeClick = (kind: WipeConfirmKind) => {
    traceBirthWipe("ui.wipe_button.click", {
      mode,
      kind,
      busy,
      activating,
      wiping: wipeConfirmWiping,
      engineLive,
      wipeBlocked,
    });

    if (wipeConfirmWiping) {
      traceBirthWipe("ui.wipe_button.blocked", { reason: "wiping", kind }, "warn");
      toast.info("Wipe already in progress…");
      return;
    }
    if (activating) {
      traceBirthWipe("ui.wipe_button.blocked", { reason: "activating", kind }, "warn");
      toast.info("Birth is starting — wipe after the sequence finishes.");
      return;
    }
    if (busy) {
      traceBirthWipe("ui.wipe_button.blocked", { reason: "busy", kind }, "warn");
      toast.info("Please wait — another birth action is in progress.");
      return;
    }
    openWipeConfirm(kind);
  };

  const stopButtonClass = cn(
    luminaInteractiveClass("danger"),
    "birth-control-dock__stop inline-flex items-center justify-center gap-1.5 font-mono text-[10px] tracking-wide uppercase",
    inline ? "birth-control-dock__stop--panel" : "min-w-[100px] gap-2",
    stopBlocked && "cursor-not-allowed opacity-70",
  );

  const stopButton = (
    <Button
      type="button"
      variant={inline ? "ghost" : "destructive"}
      size="sm"
      className={stopButtonClass}
      aria-busy={false}
      title="Stop birth training"
      onClick={handleStopClick}
    >
      <OctagonPause className={cn("shrink-0", inline ? "size-3" : "size-3.5")} aria-hidden />
      <span className={inline ? "birth-control-dock__stop-label" : undefined}>Stop birth</span>
    </Button>
  );

  return (
    <div
      className={cn(
        "birth-control-dock pointer-events-auto flex flex-wrap items-center justify-center gap-2 rounded-xl border border-white/10 bg-black/40 px-3 py-2 backdrop-blur-md",
        inline && "rounded-none border-0 bg-transparent p-0 shadow-none backdrop-blur-none",
        className,
      )}
      role="toolbar"
      aria-label="Birth phase controls"
    >
      {mode === "running" ? (
        stopButton
      ) : (
        <>
          {engineLive ? stopButton : null}
          {showStartButton ? (
            <Button
              type="button"
              className="onboarding-cta lumina-interactive inline-flex min-w-[140px] items-center justify-center gap-2 py-2 font-mono text-[10px] tracking-wide uppercase"
              onClick={() => {
                if (busy) {
                  toast.info("Please wait — another birth action is in progress.");
                  return;
                }
                onStart?.();
              }}
            >
              <Play className="size-3.5 shrink-0" aria-hidden />
              <span>Start birth</span>
            </Button>
          ) : null}
          {checkpointAvailable ? (
            <Button
              type="button"
              variant="secondary"
              size="sm"
              className={cn(
                luminaInteractiveClass("default"),
                "birth-control-dock__action inline-flex min-w-[140px] items-center justify-center gap-2 font-mono text-[10px] tracking-wide uppercase",
                busy && "cursor-not-allowed opacity-70",
              )}
              title={RESUME_CHECKPOINT_HINT}
              aria-describedby="birth-resume-checkpoint-hint"
              onClick={() => {
                if (busy) {
                  toast.info("Please wait — another birth action is in progress.");
                  return;
                }
                onResumeCheckpoint?.();
              }}
            >
              <RotateCcw className="size-3.5 shrink-0" aria-hidden />
              Resume checkpoint
            </Button>
          ) : null}
          <Button
            type="button"
            variant="outline"
            size="sm"
            className={cn(
              luminaInteractiveClass("danger"),
              "birth-control-dock__action inline-flex min-w-[140px] items-center justify-center gap-2 border-red-500/40 font-mono text-[10px] tracking-wide text-red-200 uppercase hover:bg-red-950/30",
              wipeBlocked && "cursor-not-allowed opacity-70",
            )}
            aria-busy={wipeConfirmWiping}
            title={
              activating
                ? "Birth is starting — wipe after the sequence finishes."
                : busy
                  ? "Please wait — another birth action is in progress."
                  : "Clear checkpoint, PPO weights, and progress — tick cache kept"
            }
            onPointerDown={() => {
              traceBirthWipe(
                "ui.wipe_button.pointerdown",
                { mode, kind: "reset", busy, activating, wiping: wipeConfirmWiping },
                "debug",
              );
            }}
            onClick={() => handleWipeClick("reset")}
          >
            {wipeConfirmWiping ? (
              <Loader2 className="size-3.5 shrink-0 animate-spin" aria-hidden />
            ) : (
              <Trash2 className="size-3.5 shrink-0" aria-hidden />
            )}
            Wipe birth data
          </Button>
          <Button
            type="button"
            variant="outline"
            size="sm"
            className={cn(
              luminaInteractiveClass("danger"),
              "birth-control-dock__action inline-flex min-w-[140px] items-center justify-center gap-2 border-red-600/55 bg-red-950/25 font-mono text-[10px] tracking-wide text-red-100 uppercase hover:bg-red-950/45",
              wipeBlocked && "cursor-not-allowed opacity-70",
            )}
            aria-busy={wipeConfirmWiping}
            title={
              activating
                ? "Birth is starting — wipe after the sequence finishes."
                : busy
                  ? "Please wait — another birth action is in progress."
                  : "Permanently wipe all birth data, including tick cache and enrichment"
            }
            onPointerDown={() => {
              traceBirthWipe(
                "ui.wipe_button.pointerdown",
                { mode, kind: "full", busy, activating, wiping: wipeConfirmWiping },
                "debug",
              );
            }}
            onClick={() => handleWipeClick("full")}
          >
            {wipeConfirmWiping ? (
              <Loader2 className="size-3.5 shrink-0 animate-spin" aria-hidden />
            ) : (
              <Trash2 className="size-3.5 shrink-0" aria-hidden />
            )}
            Full wipe
          </Button>
        </>
      )}
    </div>
  );
}
