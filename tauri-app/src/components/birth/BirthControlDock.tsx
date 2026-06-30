import { useState } from "react";
import { OctagonPause, Play, RotateCcw, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";
import { luminaInteractiveClass } from "@/lib/glassGlowTaxonomy";

export type BirthControlMode = "running" | "genesis";

interface BirthControlDockProps {
  mode: BirthControlMode;
  checkpointAvailable?: boolean;
  busy?: boolean;
  inline?: boolean;
  /** When false, genesis mode omits Start birth (e.g. deck uses BirthLaunchButton). */
  showStartButton?: boolean;
  onStop?: () => void;
  onStart?: () => void;
  onWipe?: () => void;
  onResumeCheckpoint?: () => void;
  className?: string;
}

export function BirthControlDock({
  mode,
  checkpointAvailable = false,
  busy = false,
  inline = false,
  showStartButton = true,
  onStop,
  onStart,
  onWipe,
  onResumeCheckpoint,
  className,
}: BirthControlDockProps) {
  const [stopOpen, setStopOpen] = useState(false);
  const [wipeStep, setWipeStep] = useState(0);

  const closeWipe = () => setWipeStep(0);

  return (
    <>
      <div
        className={cn(
          "birth-control-dock pointer-events-auto flex flex-wrap items-center justify-center gap-2 rounded-xl border border-white/10 bg-black/40 px-3 py-2 backdrop-blur-md",
          className,
        )}
        role="toolbar"
        aria-label="Birth phase controls"
      >
        {mode === "running" ? (
          <Button
            type="button"
            variant={inline ? "outline" : "destructive"}
            size="sm"
            className={cn(
              luminaInteractiveClass("danger"),
              "birth-control-dock__stop min-w-[100px] font-mono text-[10px] tracking-wide uppercase",
              inline &&
                "h-8 border-red-500/45 bg-red-950/20 text-red-200 hover:bg-red-950/35",
              busy && "opacity-70",
            )}
            aria-busy={busy}
            onClick={() => setStopOpen(true)}
          >
            <OctagonPause className="size-3.5" aria-hidden />
            Stop birth
          </Button>
        ) : (
          <>
            {showStartButton ? (
              <Button
                type="button"
                className="onboarding-cta lumina-interactive min-w-[140px] py-2 font-mono text-[10px] tracking-wide uppercase"
                disabled={busy}
                onClick={onStart}
              >
                <Play className="size-3.5" aria-hidden />
                Start birth
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
                )}
                disabled={busy}
                onClick={onResumeCheckpoint}
              >
                <RotateCcw className="size-3.5 shrink-0" aria-hidden />
                Hervat checkpoint
              </Button>
            ) : null}
            <Button
              type="button"
              variant="outline"
              size="sm"
              className={cn(
                luminaInteractiveClass("danger"),
                "birth-control-dock__action inline-flex min-w-[140px] items-center justify-center gap-2 border-red-500/40 font-mono text-[10px] tracking-wide text-red-200 uppercase hover:bg-red-950/30",
              )}
              disabled={busy}
              onClick={() => setWipeStep(1)}
            >
              <Trash2 className="size-3.5 shrink-0" aria-hidden />
              Wis birth-data
            </Button>
          </>
        )}
      </div>

      <Dialog open={stopOpen} onOpenChange={setStopOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Birth training stoppen?</DialogTitle>
            <DialogDescription>
              De huidige run wordt gestopt. Je checkpoint blijft bewaard — kies daarna Start birth
              of Wis birth-data voor een schone run.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={() => setStopOpen(false)}>
              Annuleren
            </Button>
            <Button
              type="button"
              variant="destructive"
              disabled={busy}
              onClick={() => {
                setStopOpen(false);
                onStop?.();
              }}
            >
              Stop birth
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog
        open={wipeStep > 0}
        onOpenChange={(open) => {
          if (!open) {
            closeWipe();
          }
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {wipeStep === 1 ? "Alle birth-data wissen?" : "Bevestig volledige wipe"}
            </DialogTitle>
            <DialogDescription>
              {wipeStep === 1 ? (
                <>
                  Verwijdert progress, checkpoint, caches en policies. Genesis-instellingen en setup
                  blijven behouden.
                </>
              ) : (
                <>Dit kan niet ongedaan worden gemaakt. Start daarna opnieuw met Start birth.</>
              )}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={closeWipe}>
              Annuleren
            </Button>
            {wipeStep === 1 ? (
              <Button type="button" variant="destructive" onClick={() => setWipeStep(2)}>
                Doorgaan
              </Button>
            ) : (
              <Button
                type="button"
                variant="destructive"
                disabled={busy}
                onClick={() => {
                  closeWipe();
                  onWipe?.();
                }}
              >
                Wis alles
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
