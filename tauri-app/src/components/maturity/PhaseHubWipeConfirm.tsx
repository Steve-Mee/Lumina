import { AlertTriangle, Loader2 } from "lucide-react";
import { useEffect, useRef, type MouseEvent, type PointerEvent, type ReactNode } from "react";

import { BirthPortaledDialog } from "@/components/birth/BirthPortaledDialog";
import type { HubWipeKind } from "@/components/maturity/phaseHubFormat";
import { Button } from "@/components/ui/button";
import { luminaInteractiveClass } from "@/lib/glassGlowTaxonomy";
import { cn } from "@/lib/utils";

export interface PhaseHubWipeConfirmProps {
  kind: HubWipeKind | null;
  step: 1 | 2;
  wiping: boolean;
  error: string | null;
  onCancel: () => void;
  onContinue: () => void;
  onConfirm: () => void;
}

const COPY: Record<
  HubWipeKind,
  {
    title1: string;
    keep: string;
    remove: string[];
    title2: string;
    body2: string;
    confirmLabel: string;
  }
> = {
  playground: {
    title1: "Wipe Playground data?",
    keep: "Genesis, Birth, Awakening, and frozen π* stay.",
    remove: [
      "Playground SIM tape and first-fill ledger",
      "Playground progress heartbeat",
      "Later ladder progress (Apprenticeship and after)",
    ],
    title2: "Final confirmation",
    body2: "Confirm wipe of Playground crawl data. Awakening is not re-run. You stay on Phase Hub and can Start Playground again.",
    confirmLabel: "Wipe Playground",
  },
  awakening: {
    title1: "Wipe Awakening data?",
    keep: "Birth plant, frozen π*, tick cache, and Smart Setup stay.",
    remove: [
      "Awakening live shot (child policy, holdout ledger)",
      "Evolution-proof stamp written by Awakening",
      "Later ladder progress (Playground and after)",
    ],
    title2: "Final confirmation",
    body2: "Confirm wipe of generated Awakening data. Birth is not re-run. You stay on Phase Hub and can Start Awakening again.",
    confirmLabel: "Wipe Awakening",
  },
  apprenticeship: {
    title1: "Wipe Apprenticeship data?",
    keep: "Genesis, Birth, Awakening, Playground, and frozen π* stay.",
    remove: [
      "Apprenticeship tape and session-day ledger",
      "Apprenticeship progress heartbeat",
      "Later ladder progress (Proving Ground and REAL)",
    ],
    title2: "Final confirmation",
    body2: "Confirm wipe of Apprenticeship walking data. Playground crawl is not re-run. You stay on Phase Hub and can Start Apprenticeship again.",
    confirmLabel: "Wipe Apprenticeship",
  },
  proving_ground: {
    title1: "Wipe Proving Ground data?",
    keep: "Genesis through Apprenticeship, Birth freeze, and frozen π* stay.",
    remove: [
      "Proving Ground tape and exam heartbeat",
      "This-run shadow / PromotionGate evidence",
      "Later ladder progress (REAL)",
    ],
    title2: "Final confirmation",
    body2: "Confirm wipe of the driving-test tape. Apprenticeship walk is not re-run. You stay on Phase Hub and can Start Proving Ground again.",
    confirmLabel: "Wipe Proving Ground",
  },
  birth: {
    title1: "Wipe Birth and Awakening?",
    keep: "Tick cache, split cache, enrichment, and Smart Setup stay.",
    remove: [
      "Birth curriculum, checkpoints, and PPO plant",
      "Awakening shot and later ladder progress",
    ],
    title2: "Final confirmation",
    body2: "Confirm Birth reset (history kept). You return to a blank Genesis deck and Activate Birth again.",
    confirmLabel: "Wipe Birth",
  },
  full: {
    title1: "Permanently wipe Birth and history?",
    keep: "Smart Setup stays — credentials, NT paths, and config.yaml are not wiped.",
    remove: [
      "Birth plant, checkpoints, and PPO policies",
      "Awakening shot and later ladder progress",
      "Tick cache, split cache, and enrichment cache",
    ],
    title2: "Final confirmation",
    body2: "Confirm full wipe. You restart from a blank Genesis deck. History must be loaded again. Setup is not wiped.",
    confirmLabel: "Wipe everything permanently",
  },
};

export function PhaseHubWipeConfirm({
  kind,
  step,
  wiping,
  error,
  onCancel,
  onContinue,
  onConfirm,
}: PhaseHubWipeConfirmProps) {
  const copy = kind ? COPY[kind] : null;
  const open = kind != null && copy != null;
  const confirmOnce = useRef(false);

  useEffect(() => {
    confirmOnce.current = false;
  }, [kind, step]);

  useEffect(() => {
    if (!wiping) confirmOnce.current = false;
  }, [wiping]);

  const fireConfirm = () => {
    if (wiping || confirmOnce.current) return;
    confirmOnce.current = true;
    onConfirm();
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

  const description: ReactNode = copy ? (
    <div className="space-y-3 pt-1 text-sm text-muted-foreground">
      {step === 1 ? (
        <>
          <p className="rounded-lg border border-red-500/40 bg-red-950/30 px-3 py-2 font-medium text-red-100">
            Warning: this cannot be undone.
          </p>
          <p>Will be removed:</p>
          <ul className="list-inside list-disc space-y-1 text-foreground/85">
            {copy.remove.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
          <p className="text-xs text-emerald-200/90">{copy.keep}</p>
        </>
      ) : (
        <>
          <p className="rounded-lg border border-red-500/40 bg-red-950/30 px-3 py-2 text-red-100">
            {copy.body2}
          </p>
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
      )}
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
          {step === 1 ? copy?.title1 : copy?.title2}
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
          {step === 1 ? (
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
                onContinue();
              }}
            >
              I understand — continue
            </Button>
          ) : (
            <Button
              type="button"
              variant="destructive"
              size="sm"
              disabled={wiping}
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
