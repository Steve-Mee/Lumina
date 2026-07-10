import type { ReactNode } from "react";
import { useEffect, useId } from "react";
import { createPortal } from "react-dom";
import { XIcon } from "lucide-react";

import { getLuminaOverlayRoot } from "@/lib/luminaOverlayRoot";
import { modeAccentBorderClass } from "@/lib/modePresentation";
import { cn } from "@/lib/utils";

interface BirthPortaledDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: ReactNode;
  description?: ReactNode;
  footer: ReactNode;
  className?: string;
  panelClassName?: string;
  dismissLocked?: boolean;
  shouldBlockDismiss?: () => boolean;
  onMounted?: () => void;
}

/**
 * Birth confirms — centered Lumina glass modal via #lumina-overlay-root (outside remounting decks).
 */
export function BirthPortaledDialog({
  open,
  onOpenChange,
  title,
  description,
  footer,
  className,
  panelClassName,
  dismissLocked = false,
  shouldBlockDismiss,
  onMounted,
}: BirthPortaledDialogProps) {
  const titleId = useId();
  const descId = useId();

  useEffect(() => {
    if (open) {
      onMounted?.();
    }
  }, [open, onMounted]);

  useEffect(() => {
    if (!open) {
      return;
    }
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Escape") {
        return;
      }
      if (dismissLocked || shouldBlockDismiss?.()) {
        event.preventDefault();
        return;
      }
      onOpenChange(false);
    };
    window.addEventListener("keydown", onKeyDown);
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = previousOverflow;
    };
  }, [open, dismissLocked, shouldBlockDismiss, onOpenChange]);

  if (!open || typeof document === "undefined") {
    return null;
  }

  const requestDismiss = () => {
    if (dismissLocked || shouldBlockDismiss?.()) {
      return;
    }
    onOpenChange(false);
  };

  return createPortal(
    <div
      className="dark birth-portaled-dialog-scope cockpit-shell text-foreground"
      data-mode="SIM"
      data-birth-portaled-dialog=""
    >
      <button
        type="button"
        tabIndex={-1}
        className="birth-portaled-dialog__scrim deck-overlay-scrim lumina-glass lumina-glass--overlay"
        aria-label="Sluiten"
        onClick={requestDismiss}
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={description ? descId : undefined}
        className={cn(
          "birth-portaled-dialog__panel lumina-glass lumina-glass--overlay lumina-glow-halo rounded-xl text-sm shadow-2xl outline-none",
          modeAccentBorderClass("SIM"),
          panelClassName,
        )}
        onPointerDown={(event) => event.stopPropagation()}
        onClick={(event) => event.stopPropagation()}
      >
        <button
          type="button"
          className="birth-portaled-dialog__close rounded-sm text-cyan-200/80 transition-opacity hover:text-cyan-100 focus:outline-none focus:ring-2 focus:ring-ring"
          onClick={requestDismiss}
          disabled={dismissLocked}
          aria-label="Sluiten"
        >
          <XIcon className="size-4" />
        </button>
        <div className={cn("birth-portaled-dialog__body grid gap-4 p-6", className)}>
          <div className="birth-portaled-dialog__header flex flex-col gap-1.5 pr-8 text-left">
            <h2
              id={titleId}
              className="font-mono text-base leading-snug font-medium tracking-wide text-foreground"
            >
              {title}
            </h2>
            {description ? (
              <div id={descId} className="text-sm leading-relaxed text-muted-foreground">
                {description}
              </div>
            ) : null}
          </div>
          <div className="birth-portaled-dialog__footer">{footer}</div>
        </div>
      </div>
    </div>,
    getLuminaOverlayRoot(),
  );
}
