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
                ? "Birth reset — tick cache behouden. Ga verder via Genesis."
                : "Alle birth-data gewist — klaar voor schone start."),
          );
          return;
        }
        const errorMsg =
          result.error ?? "Wissen mislukt — probeer opnieuw of herstart de backend.";
        setWipeConfirmError(errorMsg);
        toast.error(errorMsg);
      })
      .catch((err: unknown) => {
        const errorMsg = err instanceof Error ? err.message : "Wissen mislukt — onbekende fout.";
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
          toast.success("Gestopt — kies Start birth of Wis birth-data voor schone run");
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
        title="Birth training stoppen?"
        description="De huidige run wordt gestopt. Je checkpoint blijft bewaard — kies daarna Start birth of Wis birth-data voor een schone run."
        footer={
          <>
            <Button
              type="button"
              variant="outline"
              size="sm"
              className={cn(luminaInteractiveClass("ghost"), "birth-portaled-dialog__ghost font-mono text-[10px] tracking-wide uppercase")}
              onClick={closeStopConfirm}
            >
              Annuleren
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
                ? "Alle birth-data permanent wissen?"
                : "Birth reset — checkpoint wissen?"
              : "Laatste bevestiging"}
          </span>
        }
        description={
          <div className="space-y-3 pt-1 text-sm text-muted-foreground">
            {wipeConfirmStep === 1 ? (
              wipeConfirmKind === "full" ? (
                <>
                  <p className="rounded-lg border border-red-500/40 bg-red-950/30 px-3 py-2 font-medium text-red-100">
                    Waarschuwing: dit kan niet ongedaan worden gemaakt. Er is geen weg terug —
                    checkpoint, PPO-policy, tick-caches en voortgang gaan definitief verloren.
                  </p>
                  <p>Wordt verwijderd:</p>
                  <ul className="list-inside list-disc space-y-1 text-foreground/85">
                    <li>Curriculum-voortgang en stage-checkpoints</li>
                    <li>PPO-policies en birth-buffers</li>
                    <li>Tick-caches, split-cache en enrichment cache</li>
                    <li>Birth-logs en simulator-journal</li>
                    <li>Genesis charter en setup flags</li>
                  </ul>
                  <p className="text-xs">
                    Genesis-instellingen worden ook gewist — je start opnieuw via het Genesis deck.
                  </p>
                </>
              ) : (
                <>
                  <p className="rounded-lg border border-red-500/40 bg-red-950/30 px-3 py-2 font-medium text-red-100">
                    Waarschuwing: dit kan niet ongedaan worden gemaakt. Checkpoint, PPO-policy,
                    buffers en voortgang gaan definitief verloren.
                  </p>
                  <p>Wordt verwijderd:</p>
                  <ul className="list-inside list-disc space-y-1 text-foreground/85">
                    <li>Curriculum-voortgang en stage-checkpoints</li>
                    <li>PPO-policies en birth-buffers</li>
                    <li>Birth-logs en simulator-journal</li>
                    <li>Genesis charter en setup flags</li>
                  </ul>
                  <p className="text-xs text-emerald-200/90">
                    Tick-cache, split-cache en enrichment cache blijven behouden — snellere herstart.
                  </p>
                  <p className="text-xs">
                    Genesis-instellingen worden gewist — je start opnieuw via het Genesis deck.
                  </p>
                </>
              )
            ) : (
              <>
                <p className="rounded-lg border border-red-500/40 bg-red-950/30 px-3 py-2 text-red-100">
                  {wipeConfirmKind === "full"
                    ? "Bevestig dat je alle birth-trainingdata definitief wilt wissen, inclusief tick cache. Na deze actie moet je opnieuw beginnen met Start birth."
                    : "Bevestig dat je birth wilt resetten (tick cache blijft). Na deze actie moet je opnieuw beginnen via het Genesis deck."}
                </p>
                {wipeConfirmWiping ? (
                  <p
                    className="flex items-center gap-2 font-mono text-xs text-cyan-200/90"
                    role="status"
                    aria-live="polite"
                  >
                    <Loader2 className="size-4 shrink-0 animate-spin" aria-hidden />
                    Birth-data wordt gewist en gecontroleerd…
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
              Annuleren
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
                Ik begrijp het — doorgaan
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
                    Bezig met wissen…
                  </>
                ) : wipeConfirmKind === "full" ? (
                  "Definitief alles wissen"
                ) : (
                  "Definitief resetten"
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
            Birth-data gewist
          </span>
        }
        description={
          <div className="space-y-2 pt-1 text-sm text-muted-foreground">
            <p className="text-foreground/90">
              {wipeSuccess?.message ??
                "Alle birth-trainingdata is verwijderd. De status is gecontroleerd en schoon."}
            </p>
            {wipeSuccess?.removedCount != null && wipeSuccess.removedCount > 0 ? (
              <p className="font-mono text-xs text-emerald-200/80">
                Controle OK — {wipeSuccess.removedCount.toLocaleString()} artifact
                {wipeSuccess.removedCount === 1 ? "" : "en"} verwijderd.
              </p>
            ) : (
              <p className="font-mono text-xs text-emerald-200/80">
                Controle OK — geen resterende checkpoint of voortgang gevonden.
              </p>
            )}
            <p className="text-xs">Je kunt nu opnieuw starten met Start birth.</p>
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
