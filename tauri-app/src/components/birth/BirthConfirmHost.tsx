import { Loader2, OctagonPause, AlertTriangle, CheckCircle2 } from "lucide-react";
import { toast } from "sonner";

import { BirthPortaledDialog } from "@/components/birth/BirthPortaledDialog";
import { Button } from "@/components/ui/button";
import { luminaInteractiveClass } from "@/lib/glassGlowTaxonomy";
import { traceBirthWipe } from "@/lib/birthWipeTrace";
import { cn } from "@/lib/utils";
import { useBirthStore } from "@/store/birthStore";
import { useBirthUiStore } from "@/store/birthUiStore";

/**
 * Global birth confirm layer — mounted once from App so dialogs survive genesis deck remounts.
 */
export function BirthConfirmHost() {
  const wipeConfirmStep = useBirthUiStore((s) => s.wipeConfirmStep);
  const wipeConfirmKind = useBirthUiStore((s) => s.wipeConfirmKind);
  const wipeConfirmWiping = useBirthUiStore((s) => s.wipeConfirmWiping);
  const wipeConfirmError = useBirthUiStore((s) => s.wipeConfirmError);
  const wipeSuccess = useBirthUiStore((s) => s.wipeSuccess);
  const stopConfirmOpen = useBirthUiStore((s) => s.stopConfirmOpen);
  const stopConfirmStopping = useBirthUiStore((s) => s.stopConfirmStopping);
  const shouldBlockDismiss = useBirthUiStore((s) => s.shouldBlockDismiss);
  const closeWipeConfirm = useBirthUiStore((s) => s.closeWipeConfirm);
  const setWipeConfirmStep = useBirthUiStore((s) => s.setWipeConfirmStep);
  const setWipeConfirmWiping = useBirthUiStore((s) => s.setWipeConfirmWiping);
  const setWipeConfirmError = useBirthUiStore((s) => s.setWipeConfirmError);
  const setWipeSuccess = useBirthUiStore((s) => s.setWipeSuccess);
  const closeStopConfirm = useBirthUiStore((s) => s.closeStopConfirm);
  const setStopConfirmStopping = useBirthUiStore((s) => s.setStopConfirmStopping);

  const handleWipeOpenChange = (open: boolean) => {
    traceBirthWipe("ui.wipe_dialog.open_change", {
      open,
      wipeConfirmStep,
      wiping: wipeConfirmWiping,
      source: "BirthConfirmHost",
    });
    if (!open && wipeConfirmWiping) {
      return;
    }
    if (!open && shouldBlockDismiss()) {
      traceBirthWipe("ui.wipe_dialog.dismiss_suppressed", { wipeConfirmStep });
      return;
    }
    if (!open) {
      closeWipeConfirm();
    }
  };

  const handleStopOpenChange = (open: boolean) => {
    if (!open && shouldBlockDismiss()) {
      return;
    }
    if (!open) {
      closeStopConfirm();
    }
  };

  const runWipe = () => {
    const preserveTickCache = wipeConfirmKind === "reset";
    traceBirthWipe("ui.wipe_confirm.click", {
      wipeConfirmStep,
      wiping: wipeConfirmWiping,
      kind: wipeConfirmKind,
      preserveTickCache,
    });
    if (wipeConfirmWiping) {
      return;
    }
    setWipeConfirmError(null);
    setWipeConfirmWiping(true);
    traceBirthWipe("ui.wipe_handler.start", { kind: wipeConfirmKind, preserveTickCache });
    void useBirthStore
      .getState()
      .wipeBirthData({ preserveTickCache })
      .then((result) => {
        traceBirthWipe(
          "ui.wipe_handler.result",
          {
            ok: result.ok,
            error: result.error,
            removedCount: result.removedCount,
            message: result.message,
          },
          result.ok ? "info" : "error",
        );
        if (result.ok) {
          setWipeConfirmStep(0);
          setWipeSuccess(result);
          toast.success(
            result.message ??
              (preserveTickCache
                ? "Birth reset — tick cache kept. Continue via Genesis."
                : "All birth data wiped — ready for a clean start."),
          );
          return;
        }
        const errorMsg =
          result.error ?? "Wipe failed — try again or restart the backend.";
        setWipeConfirmError(errorMsg);
        toast.error(errorMsg);
      })
      .catch((err: unknown) => {
        const errorMsg = err instanceof Error ? err.message : "Wipe failed — unknown error.";
        traceBirthWipe("ui.wipe_handler.exception", { error: errorMsg }, "error");
        setWipeConfirmError(errorMsg);
        toast.error(errorMsg);
      })
      .finally(() => {
        setWipeConfirmWiping(false);
        traceBirthWipe("ui.wipe_handler.finished");
      });
  };

  const confirmStop = () => {
    closeStopConfirm();
    setStopConfirmStopping(true);
    void useBirthStore
      .getState()
      .stopBirthRun()
      .then((ok) => {
        if (ok) {
          toast.success("Stopped — choose Start birth or wipe for a clean run");
          return;
        }
        toast.error(useBirthStore.getState().pollError ?? "Stop failed");
      })
      .finally(() => setStopConfirmStopping(false));
  };

  return (
    <>
      <BirthPortaledDialog
        open={stopConfirmOpen}
        onOpenChange={handleStopOpenChange}
        shouldBlockDismiss={shouldBlockDismiss}
        onMounted={() => traceBirthWipe("ui.stop_dialog.mounted", { source: "BirthConfirmHost" })}
        title="Stop birth training?"
        description="The current run will stop. Your checkpoint is kept — then choose Start birth or wipe for a clean run."
        footer={
          <>
            <Button
              type="button"
              variant="outline"
              size="sm"
              className={cn(luminaInteractiveClass("ghost"), "birth-portaled-dialog__ghost font-mono text-[10px] tracking-wide uppercase")}
              onClick={closeStopConfirm}
            >
              Cancel
            </Button>
            <Button
              type="button"
              variant="destructive"
              size="sm"
              disabled={stopConfirmStopping}
              className={cn(luminaInteractiveClass("danger"), "birth-portaled-dialog__danger font-mono text-[10px] tracking-wide uppercase")}
              onClick={confirmStop}
            >
              <OctagonPause className="mr-2 size-3.5" aria-hidden />
              Stop birth
            </Button>
          </>
        }
      />

      <BirthPortaledDialog
        open={wipeConfirmStep > 0}
        onOpenChange={handleWipeOpenChange}
        dismissLocked={wipeConfirmWiping}
        shouldBlockDismiss={shouldBlockDismiss}
        onMounted={() =>
          traceBirthWipe("ui.wipe_dialog.mounted", {
            wipeConfirmStep,
            kind: wipeConfirmKind,
            source: "BirthConfirmHost",
          })
        }
        title={
          <span className="flex items-center gap-2 text-red-200">
            <AlertTriangle className="size-5 shrink-0 text-red-400" aria-hidden />
            {wipeConfirmStep === 1
              ? wipeConfirmKind === "full"
                ? "Permanently wipe all birth data?"
                : "Birth reset — wipe checkpoint?"
              : "Final confirmation"}
          </span>
        }
        description={
          <div className="space-y-3 pt-1 text-sm text-muted-foreground">
            {wipeConfirmStep === 1 ? (
              wipeConfirmKind === "full" ? (
                <>
                  <p className="rounded-lg border border-red-500/40 bg-red-950/30 px-3 py-2 font-medium text-red-100">
                    Warning: this cannot be undone. Checkpoint, PPO policy, tick caches, and
                    progress will be permanently lost.
                  </p>
                  <p>Will be removed:</p>
                  <ul className="list-inside list-disc space-y-1 text-foreground/85">
                    <li>Curriculum progress and stage checkpoints</li>
                    <li>PPO policies and birth buffers</li>
                    <li>Tick caches, split cache, and enrichment cache</li>
                    <li>Birth logs and simulator journal</li>
                    <li>Genesis charter and setup flags</li>
                  </ul>
                  <p className="text-xs">
                    Genesis settings are wiped too — restart from the Genesis deck.
                  </p>
                </>
              ) : (
                <>
                  <p className="rounded-lg border border-red-500/40 bg-red-950/30 px-3 py-2 font-medium text-red-100">
                    Warning: this cannot be undone. Checkpoint, PPO policy, buffers, and progress
                    will be permanently lost.
                  </p>
                  <p>Will be removed:</p>
                  <ul className="list-inside list-disc space-y-1 text-foreground/85">
                    <li>Curriculum progress and stage checkpoints</li>
                    <li>PPO policies and birth buffers</li>
                    <li>Birth logs and simulator journal</li>
                    <li>Genesis charter and setup flags</li>
                  </ul>
                  <p className="text-xs text-emerald-200/90">
                    Tick cache, split cache, and enrichment cache are kept — faster restart.
                  </p>
                  <p className="text-xs">
                    Genesis settings are wiped — restart from the Genesis deck.
                  </p>
                </>
              )
            ) : (
              <>
                <p className="rounded-lg border border-red-500/40 bg-red-950/30 px-3 py-2 text-red-100">
                  {wipeConfirmKind === "full"
                    ? "Confirm permanent wipe of all birth training data, including tick cache. You must start again with Activate birth."
                    : "Confirm birth reset (tick cache kept). You must start again from the Genesis deck."}
                </p>
                {wipeConfirmWiping ? (
                  <p
                    className="flex items-center gap-2 font-mono text-xs text-cyan-200/90"
                    role="status"
                    aria-live="polite"
                  >
                    <Loader2 className="size-4 shrink-0 animate-spin" aria-hidden />
                    Wiping birth data and verifying…
                  </p>
                ) : null}
                {wipeConfirmError ? (
                  <p
                    className="rounded-lg border border-red-500/35 bg-red-950/20 px-3 py-2 text-sm text-red-200"
                    role="alert"
                  >
                    {wipeConfirmError}
                  </p>
                ) : null}
              </>
            )}
          </div>
        }
        footer={
          <>
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={wipeConfirmWiping}
              className={cn(luminaInteractiveClass("ghost"), "birth-portaled-dialog__ghost font-mono text-[10px] tracking-wide uppercase")}
              onClick={closeWipeConfirm}
            >
              Cancel
            </Button>
            {wipeConfirmStep === 1 ? (
              <Button
                type="button"
                variant="destructive"
                size="sm"
                className={cn(luminaInteractiveClass("danger"), "birth-portaled-dialog__danger font-mono text-[10px] tracking-wide uppercase")}
                onClick={() => {
                  setWipeConfirmStep(2);
                  traceBirthWipe("ui.wipe_dialog.step", { step: 2 });
                }}
              >
                I understand — continue
              </Button>
            ) : (
              <Button
                type="button"
                variant="destructive"
                size="sm"
                disabled={wipeConfirmWiping}
                className={cn(luminaInteractiveClass("danger"), "birth-portaled-dialog__danger font-mono text-[10px] tracking-wide uppercase")}
                onClick={runWipe}
              >
                {wipeConfirmWiping ? (
                  <>
                    <Loader2 className="mr-2 size-4 animate-spin" aria-hidden />
                    Wiping…
                  </>
                ) : wipeConfirmKind === "full" ? (
                  "Wipe everything permanently"
                ) : (
                  "Confirm reset"
                )}
              </Button>
            )}
          </>
        }
      />

      <BirthPortaledDialog
        open={wipeSuccess != null}
        onOpenChange={(open) => {
          if (!open) {
            setWipeSuccess(null);
          }
        }}
        onMounted={() => traceBirthWipe("ui.wipe_success_dialog.mounted", { source: "BirthConfirmHost" })}
        title={
          <span className="flex items-center gap-2 text-emerald-200">
            <CheckCircle2 className="size-5 shrink-0 text-emerald-400" aria-hidden />
            Birth data wiped
          </span>
        }
        description={
          <div className="space-y-2 pt-1 text-sm text-muted-foreground">
            <p className="text-foreground/90">
              {wipeSuccess?.message ??
                "All birth training data was removed. Status verified clean."}
            </p>
            {wipeSuccess?.removedCount != null && wipeSuccess.removedCount > 0 ? (
              <p className="font-mono text-xs text-emerald-200/80">
                Check OK — {wipeSuccess.removedCount.toLocaleString()} artifact
                {wipeSuccess.removedCount === 1 ? "" : "s"} removed.
              </p>
            ) : (
              <p className="font-mono text-xs text-emerald-200/80">
                Check OK — no remaining checkpoint or progress found.
              </p>
            )}
            <p className="text-xs">You can restart with Activate birth.</p>
          </div>
        }
        footer={
          <Button
            type="button"
            size="sm"
            className="birth-portaled-dialog__success onboarding-cta font-mono text-[10px] tracking-wide uppercase"
            onClick={() => setWipeSuccess(null)}
          >
            Begrepen
          </Button>
        }
      />
    </>
  );
}
