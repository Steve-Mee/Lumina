/**
 * Birth-surface Twin micro training — non-blocking control + glass modal.
 * Primary placement: Neural Genesis card toolbar (right slot).
 * Dual-channel when session starts; does not block Birth activation.
 */
import { useCallback, useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { Brain, XIcon } from "lucide-react";
import { toast } from "sonner";

import { TwinMicroSessionCard } from "@/components/operations/TwinMicroSessionCard";
import { Button } from "@/components/ui/button";
import { selectApiKeyConfigured, useApiKeyStore } from "@/store/apiKeyStore";
import { fetchTwinReadiness, type TwinReadiness } from "@/lib/twinClient";
import { getLuminaOverlayRoot } from "@/lib/luminaOverlayRoot";
import { luminaInteractiveClass } from "@/lib/glassGlowTaxonomy";
import { modeAccentBorderClass } from "@/lib/modePresentation";
import { cn } from "@/lib/utils";
import "@/styles/twinTraining.css";

const POLL_MS = 30_000;

export type BirthTwinMicroVariant = "genesis-toolbar" | "compact";

export function BirthTwinMicroHost({
  className,
  variant = "genesis-toolbar",
}: {
  className?: string;
  /** genesis-toolbar = right slot of Neural Genesis card; compact = mission HUD chip */
  variant?: BirthTwinMicroVariant;
}) {
  const apiKeyConfigured = useApiKeyStore(selectApiKeyConfigured);
  const [readiness, setReadiness] = useState<TwinReadiness | null>(null);
  const [open, setOpen] = useState(false);

  const refresh = useCallback(async () => {
    if (!apiKeyConfigured) {
      setReadiness(null);
      return;
    }
    try {
      setReadiness(await fetchTwinReadiness());
    } catch {
      /* soft — vault key may not be in store yet */
    }
  }, [apiKeyConfigured]);

  useEffect(() => {
    void refresh();
    const t = window.setInterval(() => void refresh(), POLL_MS);
    return () => window.clearInterval(t);
  }, [refresh]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  const baseReady = Boolean(readiness?.birth_ready || readiness?.base_trained);

  const onChipClick = () => {
    if (!apiKeyConfigured) {
      toast.info("API-key nodig (Operator Vault → Admin key) voor Twin micro.");
      return;
    }
    if (!baseReady) {
      toast.info("Eerst Twin base training in Operator Vault afronden.");
      return;
    }
    setOpen(true);
  };

  const chipState = !apiKeyConfigured ? "idle" : !baseReady ? "warn" : "ok";
  const chipLabel = !baseReady ? "Twin base" : "Twin train";
  const chipTip = !baseReady
    ? "Base curriculum incomplete — open Operator Vault → Twin"
    : "3 korte labels · app + Telegram · ~2 min · optioneel tijdens Birth";

  return (
    <>
      <div className={cn("birth-twin-micro-host", className)}>
        <button
          type="button"
          className={cn(
            luminaInteractiveClass("ghost"),
            "birth-twin-micro-chip",
            variant === "genesis-toolbar"
              ? "birth-twin-micro-chip--toolbar"
              : "birth-command-bar__tool-btn birth-twin-micro-chip--compact",
          )}
          data-state={chipState}
          title={chipTip}
          aria-label={chipTip}
          onClick={onChipClick}
        >
          <Brain className="size-3.5 shrink-0" aria-hidden />
          <span>{chipLabel}</span>
        </button>
      </div>

      {open && typeof document !== "undefined"
        ? createPortal(
            <div
              className="dark birth-portaled-dialog-scope cockpit-shell text-foreground"
              data-mode="SIM"
              data-birth-twin-micro-modal=""
            >
              <button
                type="button"
                tabIndex={-1}
                className="birth-portaled-dialog__scrim deck-overlay-scrim lumina-glass lumina-glass--overlay"
                aria-label="Sluiten"
                onClick={() => setOpen(false)}
              />
              <div
                role="dialog"
                aria-modal="true"
                aria-label="Twin micro training"
                className={cn(
                  "birth-twin-micro-modal lumina-glass lumina-glass--overlay lumina-glow-halo rounded-xl shadow-2xl outline-none",
                  modeAccentBorderClass("SIM"),
                )}
                onPointerDown={(e) => e.stopPropagation()}
                onClick={(e) => e.stopPropagation()}
              >
                <div className="birth-twin-micro-modal__header">
                  <div className="min-w-0 flex-1">
                    <p className="twin-training-panel__eyebrow">Birth · dual channel</p>
                    <p className="twin-training-panel__title">Twin micro training</p>
                  </div>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon-xs"
                    className="shrink-0 text-cyan-200/80 hover:text-cyan-100"
                    aria-label="Sluiten"
                    onClick={() => setOpen(false)}
                  >
                    <XIcon className="size-4" />
                  </Button>
                </div>
                <p className="twin-training-copy mb-3">
                  Optioneel tijdens Birth — 3 korte A/B/C/D labels. Twin leert direct. Geen
                  pre-approval; base curriculum blijft in de Vault.
                </p>
                <TwinMicroSessionCard
                  onDone={() => {
                    void refresh();
                    toast.success("Micro-sessie klaar — Twin bijgewerkt");
                  }}
                />
              </div>
            </div>,
            getLuminaOverlayRoot(),
          )
        : null}
    </>
  );
}
