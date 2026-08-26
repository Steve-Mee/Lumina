/** Shared Systems Go modal chrome (vault / risk-envelope parity). */
import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

export function SystemsGoDialog({
  open,
  eyebrow,
  title,
  titleId,
  children,
  primaryLabel,
  primaryBusyLabel,
  busy,
  onPrimary,
  secondaryLabel,
  onSecondary,
  footnote,
  className,
}: {
  open: boolean;
  eyebrow: string;
  title: string;
  titleId: string;
  children: ReactNode;
  primaryLabel: string;
  primaryBusyLabel?: string;
  busy?: boolean;
  onPrimary: () => void;
  secondaryLabel: string;
  onSecondary: () => void;
  footnote?: string;
  className?: string;
}) {
  if (!open) return null;

  const descId = `${titleId}-desc`;

  return (
    <div
      className="systems-go-dialog-scrim"
      role="dialog"
      aria-modal="true"
      aria-labelledby={titleId}
      aria-describedby={descId}
    >
      <div className={cn("systems-go-dialog lumina-glass lumina-glass--overlay", className)}>
        <header className="systems-go-dialog__toolbar">
          <p className="systems-go-dialog__eyebrow">{eyebrow}</p>
          <h2 id={titleId} className="systems-go-dialog__title">
            {title}
          </h2>
        </header>
        <div className="systems-go-dialog__body">
          <div id={descId}>{children}</div>
          <div className="systems-go-dialog__actions">
            <button
              type="button"
              className="onboarding-cta w-full rounded-md py-2.5 text-[0.7rem]"
              disabled={busy}
              onClick={onPrimary}
              autoFocus
            >
              {busy ? primaryBusyLabel || primaryLabel : primaryLabel}
            </button>
            <button
              type="button"
              className="onboarding-btn-secondary w-full rounded-md py-2 font-mono text-[0.55rem] tracking-wider uppercase"
              disabled={busy}
              onClick={onSecondary}
            >
              {secondaryLabel}
            </button>
          </div>
          {footnote ? (
            <p className="systems-go-dialog__footnote">{footnote}</p>
          ) : null}
        </div>
      </div>
    </div>
  );
}
