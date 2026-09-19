import type { ReactNode } from "react";
import { Trash2 } from "lucide-react";


import { CharterTile, RecoveryActionCard } from "@/components/birth/BirthGenesisDeckPrimitives";
import { BirthLaunchButton } from "@/components/birth/BirthLaunchButton";
import { helpFor } from "@/lib/helpTexts";
import type { MaturityHubPayload } from "@/lib/maturationClient";
import { cn } from "@/lib/utils";
import {
  formatAwakeningProbe,
  HUB_WIPE_CARDS,
  hubVerdict,
  phaseLabel,
  phaseStartIncomplete,
  proofLabel,
  startPhaseCtaLabel,
  type HubWipeKind,
} from "@/components/maturity/phaseHubFormat";
import { resolveHubCharterTiles } from "@/components/maturity/phaseHubTiles";

export interface PhaseHubDeckProps {
  hub: MaturityHubPayload | null;
  busy: boolean;
  runnerActive: boolean;
  onStartNext: () => void;
  onOpenDeck: () => void;
  onWipe: (kind: HubWipeKind) => void;
  children?: ReactNode;
}

export function PhaseHubDeck({
  hub,
  busy,
  runnerActive,
  onStartNext,
  onOpenDeck,
  onWipe,
  children,
}: PhaseHubDeckProps) {
  const nextPhase = hub?.next_phase ?? null;
  const nextSpec = nextPhase ? hub?.phase_specs?.[nextPhase] : null;
  const tiles = resolveHubCharterTiles(hub);
  const missing = hub?.exit_eval && !hub.exit_eval.ok ? hub.exit_eval.missing ?? [] : [];
  const ctaLocked = busy || runnerActive || !nextPhase;
  const running = Boolean(hub?.active_phase) || runnerActive;
  const retry = phaseStartIncomplete(hub);
  const probeLine = formatAwakeningProbe(hub?.focus_learned);

  return (
    <div className="phase-hub-deck flex min-h-0 flex-1 flex-col overflow-hidden">
      <p className="phase-hub-verdict px-1">{hubVerdict(hub)}</p>

      <div className="phase-hub-body flex min-h-0 flex-1 flex-col gap-2 overflow-hidden px-1">
        <div className="genesis-charter-tile-grid phase-hub-kpi-grid shrink-0">
          {tiles.map((tile) => (
            <CharterTile
              key={tile.label}
              label={tile.label}
              value={tile.value}
              tip={tile.tip}
              footnote={tile.footnote}
            />
          ))}
        </div>

        <section className="phase-hub-next-card risk-envelope-field-card shrink-0">
          <div className="flex flex-wrap items-end justify-between gap-2">
            <div className="min-w-0 flex-1">
              <p className="risk-envelope-field-label">Next</p>
              {running ? (
                <p className="font-mono text-sm text-amber-200/90">
                  Running {phaseLabel(hub?.active_phase)}…
                </p>
              ) : nextSpec ? (
                <>
                  <p className="text-base font-medium tracking-wide text-cyan-100">{nextSpec.label}</p>
                  <p
                    className={
                      retry
                        ? "font-mono text-[11px] leading-snug text-rose-200/90"
                        : "font-mono text-[11px] leading-snug text-muted-foreground"
                    }
                  >
                    {retry
                      ? `Incomplete — ${missing.length > 0 ? missing.map(proofLabel).join(", ") : "exit proofs still open"}. ${probeLine ?? "Click Retry; floors stay fail-closed."}`
                      : nextSpec.human_goal}
                  </p>
                </>
              ) : (
                <p className="font-mono text-sm text-emerald-200/90">
                  Continuum complete — REAL path is human-gated.
                </p>
              )}
            </div>
            {missing.length > 0 ? (
              <ul className="flex flex-wrap gap-1.5">
                {missing.map((code) => (
                  <li key={code} className="risk-envelope-status-chip" data-state="warn">
                    {proofLabel(code)}
                  </li>
                ))}
              </ul>
            ) : null}
          </div>
        </section>

        {children}

        <section className="phase-hub-wipe shrink-0">
          <p className="risk-envelope-field-label text-rose-200/80">Danger</p>
          <p className="mt-0.5 font-mono text-[10px] leading-snug text-muted-foreground">
            Restart resumes here. Birth is not re-run unless you wipe Birth or Full wipe.
          </p>
          <div className="genesis-recovery-action-grid genesis-recovery-action-grid--3 mt-2">
            {HUB_WIPE_CARDS.map((card) => (
              <RecoveryActionCard
                key={card.kind}
                label={card.label}
                tip={card.tip}
                hint={card.hint}
                tone={card.tone}
              >
                <button
                  type="button"
                  className={cn(
                    "genesis-recovery-action-card__btn",
                    card.tone === "danger"
                      ? "genesis-recovery-action-card__btn--danger"
                      : "genesis-recovery-action-card__btn--warn",
                    (busy || runnerActive) && "cursor-not-allowed opacity-70",
                  )}
                  disabled={busy || runnerActive}
                  onClick={() => onWipe(card.kind)}
                >
                  <Trash2 className="size-3.5 shrink-0" aria-hidden />
                  <span>{card.label}</span>
                </button>
              </RecoveryActionCard>
            ))}
          </div>
        </section>
      </div>

      <div className="risk-envelope-cta-bar genesis-launch-cta phase-hub-cta shrink-0">
        <p className="mb-1.5 text-center font-mono text-[0.5rem] tracking-[0.12em] text-white/30 uppercase">
          {helpFor("maturity_ladder")
            ? "Click to start Awakening · preference above is not a gate"
            : "Click to start · REAL still needs you"}
        </p>
        <div className="phase-hub-cta__row">
          {nextPhase && nextPhase !== "birth" ? (
            <BirthLaunchButton
              activating={runnerActive}
              disabled={ctaLocked}
              idleLabel={startPhaseCtaLabel(nextPhase, { retry }).toUpperCase()}
              onClick={onStartNext}
              className="phase-hub-cta__primary"
            />
          ) : (
            <p className="flex-1 text-center font-mono text-[11px] text-muted-foreground">
              {nextPhase === "birth" ? "Start Birth from the Birth screen." : "No next phase."}
            </p>
          )}
          <button
            type="button"
            className="genesis-recovery-action-card__btn genesis-recovery-action-card__btn--idle phase-hub-cta__deck"
            onClick={onOpenDeck}
          >
            <span>Open Command Deck</span>
          </button>
        </div>
      </div>
    </div>
  );
}
