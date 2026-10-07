import { AlertTriangle, Loader2 } from "lucide-react";
import { useEffect, useRef, useState, type MouseEvent, type PointerEvent, type ReactNode } from "react";

import { BirthPortaledDialog } from "@/components/birth/BirthPortaledDialog";
import type { HubWipeKind } from "@/components/maturity/phaseHubFormat";
import { WIPE_CONFIRM_COPY, WIPE_CONFIRM_PHRASES, wipePhraseMatches } from "@/components/maturity/phaseWipeCopy";
import { Button } from "@/components/ui/button";
import { luminaInteractiveClass } from "@/lib/glassGlowTaxonomy";
import { cn } from "@/lib/utils";

export interface PhaseHubWipeConfirmProps {
  kind: HubWipeKind | null;
  wiping: boolean;
  error: string | null;
  onCancel: () => void;
  onConfirm: (phrase: string) => void;
}

export function PhaseHubWipeConfirm({
  kind,
  wiping,
  error,
  onCancel,
  onConfirm,
}: PhaseHubWipeConfirmProps) {
  const copy = kind ? WIPE_CONFIRM_COPY[kind] : null;
  const open = kind != null && copy != null;
  const confirmOnce = useRef(false);
  const phraseRef = useRef<HTMLInputElement>(null);
  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [typed, setTyped] = useState("");
  const requiredPhrase = kind ? WIPE_CONFIRM_PHRASES[kind] : "";

  useEffect(() => {
    confirmOnce.current = false;
    setStep(1);
    setTyped("");
  }, [kind]);

  useEffect(() => {
    if (!wiping) confirmOnce.current = false;
  }, [wiping]);

  useEffect(() => {
    if (step !== 3) return;
    phraseRef.current?.focus();
  }, [step, kind]);

  const phraseOk = kind != null && wipePhraseMatches(kind, typed);

  const fireConfirm = () => {
    if (!kind || wiping || confirmOnce.current || !phraseOk) return;
    confirmOnce.current = true;
    onConfirm(typed.trim());
  };

  const confirmPointer = {
    onPointerDown: (e: PointerEvent<HTMLButtonElement>) => e.stopPropagation(),
    onPointerUp: (e: PointerEvent<HTMLButtonElement>) => {
      e.preventDefault();
      e.stopPropagation();
      if (e.button !== 0) return;
      fireConfirm();
    },
    onClick: (e: MouseEvent<HTMLButtonElement>) => {
      e.preventDefault();
      e.stopPropagation();
      fireConfirm();
    },
  };

  const title =
    step === 1 ? copy?.title1 : step === 2 ? copy?.title2 : copy?.title3;

  const description: ReactNode = copy ? (
    <div className="space-y-3 pt-1 text-sm text-muted-foreground">
      {step === 1 ? (
        <>
          <p className="rounded-lg border border-red-500/40 bg-red-950/30 px-3 py-2 font-medium text-red-100">
            Warning 1 of 3: this cannot be undone.
          </p>
          <p>Will be removed:</p>
          <ul className="list-inside list-disc space-y-1 text-foreground/85">
            {copy.remove.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
          <p className="text-xs text-emerald-200/90">{copy.keep}</p>
        </>
      ) : null}
      {step === 2 ? (
        <p className="rounded-lg border border-red-500/40 bg-red-950/30 px-3 py-2 text-red-100">
          Warning 2 of 3: {copy.body2}
        </p>
      ) : null}
      {step === 3 ? (
        <>
          <p className="rounded-lg border border-red-500/40 bg-red-950/30 px-3 py-2 text-red-100">
            Warning 3 of 3: {copy.body3}
          </p>
          <label className="block text-xs text-red-100/90">
            Type this phrase in the box
            <span className="mt-1 block font-mono text-sm tracking-wide text-[var(--status-warn-fg)]">
              {requiredPhrase}
            </span>
            <input
              ref={phraseRef}
              type="text"
              className="birth-portaled-dialog__phrase"
              value={typed}
              placeholder={requiredPhrase}
              autoComplete="off"
              autoCorrect="off"
              spellCheck={false}
              disabled={wiping}
              aria-label="Wipe confirmation phrase"
              onChange={(e) => setTyped(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  fireConfirm();
                }
              }}
            />
          </label>
          {wiping ? (
            <p
              className="flex items-center gap-2 font-mono text-xs text-cyan-200/90"
              role="status"
              aria-live="polite"
            >
              <Loader2 className="size-4 shrink-0 animate-spin" aria-hidden />
              Wiping and verifying…
            </p>
          ) : null}
          {error ? (
            <p
              className="rounded-lg border border-red-500/35 bg-red-950/20 px-3 py-2 text-sm text-red-200"
              role="alert"
            >
              {error}
            </p>
          ) : null}
        </>
      ) : null}
    </div>
  ) : null;

  return (
    <BirthPortaledDialog
      open={open}
      onOpenChange={(next) => {
        if (!next) onCancel();
      }}
      dismissLocked={false}
      title={
        <span className="flex items-center gap-2 text-red-200">
          <AlertTriangle className="size-5 shrink-0 text-red-400" aria-hidden />
          {title}
        </span>
      }
      description={description}
      footer={
        <>
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={wiping}
            className={cn(
              luminaInteractiveClass("ghost"),
              "birth-portaled-dialog__ghost font-mono text-[10px] tracking-wide uppercase",
            )}
            onClick={onCancel}
          >
            Cancel
          </Button>
          {step < 3 ? (
            <Button
              type="button"
              variant="destructive"
              size="sm"
              className={cn(
                luminaInteractiveClass("danger"),
                "birth-portaled-dialog__danger pointer-events-auto font-mono text-[10px] tracking-wide uppercase",
              )}
              onPointerDown={(e) => e.stopPropagation()}
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                setStep((current) => (current === 1 ? 2 : 3));
              }}
            >
              {step === 1 ? "I understand — continue" : "I accept the loss — continue"}
            </Button>
          ) : (
            <Button
              type="button"
              variant="destructive"
              size="sm"
              disabled={wiping || !phraseOk}
              className={cn(
                luminaInteractiveClass("danger"),
                "birth-portaled-dialog__danger pointer-events-auto font-mono text-[10px] tracking-wide uppercase",
              )}
              {...confirmPointer}
            >
              {wiping ? (
                <>
                  <Loader2 className="mr-2 size-4 animate-spin" aria-hidden />
                  Wiping…
                </>
              ) : (
                copy?.confirmLabel
              )}
            </Button>
          )}
        </>
      }
    />
  );
}
